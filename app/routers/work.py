import json
import math
from datetime import datetime, date as date_type
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.services.business_date import (
    calc_business_date,
    calc_business_date_detailed,
    next_business_day,
    next_business_day_detailed,
)
from app.services.field_users import classify_leader
from app.services.missing_boundary import recompute_is_missing_for_past_business_dates

router = APIRouter(tags=["作業記録"])


def _touch_updated(unit: models.WorkUnit) -> None:
    """一覧の並び（updated_at desc）用。保存直前に呼ぶ。"""
    unit.updated_at = datetime.utcnow()


# ─── ヘルパー ────────────────────────────────────────────────

def _opt_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def _parse_lines_json(raw: Optional[str]) -> List[dict]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: List[dict] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        lb = str(it.get("label", "")).strip()
        v = it.get("value")
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if lb and math.isfinite(fv):
            out.append({"label": lb, "value": fv})
    return out


def _lines_json_dumps(lines: List[dict]) -> Optional[str]:
    if not lines:
        return None
    return json.dumps(lines, ensure_ascii=False)


def _join_line_labels(lines: List[dict], sep: str = " · ") -> Optional[str]:
    if not lines:
        return None
    return sep.join(str(x["label"]) for x in lines)


def _strict_lines_from_body(
    rows: List[schemas.WorkLineIn],
) -> Tuple[List[dict], Optional[str]]:
    """lines 指定時。空行は無視。ラベルだけ／数量だけの行はエラー。"""
    complete: List[dict] = []
    for row in rows:
        lb = (row.label or "").strip()
        v = row.value
        if not lb and v is None:
            continue
        if not lb and v is not None:
            return None, "数量だけ入力された行があります。名前と数量をセットで入力してください"
        if lb and v is None:
            return None, "名前だけ入力された行があります。数量も入力してください"
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return None, "数量の形式が不正な行があります"
        if not math.isfinite(fv):
            return None, "数量の形式が不正な行があります"
        complete.append({"label": lb, "value": fv})
    return complete, None


def _planned_lines_for_response(unit: models.WorkUnit, im: str) -> List[dict]:
    parsed = _parse_lines_json(getattr(unit, "planned_lines_json", None))
    if parsed:
        return parsed
    v = unit.planned_value
    if v is None or not math.isfinite(float(v)):
        return []
    fv = float(v)
    if im == "logistics":
        lab = _opt_str(unit.planned_work_label) or _opt_str(unit.planned_work_type)
        if not lab:
            return []
        return [{"label": lab, "value": fv}]
    n = (unit.planned_item_name or "").strip()
    if not n:
        return []
    return [{"label": n, "value": fv}]


def _actual_lines_for_response(unit: models.WorkUnit, im: str) -> List[dict]:
    parsed = _parse_lines_json(getattr(unit, "actual_lines_json", None))
    if parsed:
        return parsed
    v = unit.actual_value
    if v is None or not math.isfinite(float(v)):
        return []
    fv = float(v)
    if im == "logistics":
        lab = _opt_str(unit.actual_work_label) or _opt_str(unit.actual_work_type)
        if not lab:
            return []
        return [{"label": lab, "value": fv}]
    n = (unit.actual_item_name or "").strip()
    if not n:
        return []
    return [{"label": n, "value": fv}]


def _norm_input_mode(settings: models.CompanySettings) -> str:
    raw = getattr(settings, "input_mode", None) or "manufacturing"
    x = str(raw).strip().lower()
    return "logistics" if x == "logistics" else "manufacturing"


def _aggregate_line_quantities(lines: List[dict]) -> dict:
    """ラベル別数量（同一ラベル複数行は合算）。空ラベルは無視。"""
    out: dict = {}
    for row in lines:
        if not isinstance(row, dict):
            continue
        lb = str(row.get("label", "")).strip()
        if not lb:
            continue
        try:
            v = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        out[lb] = out.get(lb, 0.0) + v
    return out


def _planned_actual_line_mismatch(unit: models.WorkUnit, im: str) -> bool:
    """
    予告・実績の明細が一致しない（B：結果不備）。
    - ラベル集合が異なる
    - 同一集合でもラベルごとの数量が異なる
    両方とも明細が空のときは比較しない（合計のみのレコードは total diff に委ねる）。
    """
    pl = _planned_lines_for_response(unit, im)
    al = _actual_lines_for_response(unit, im)
    dp = _aggregate_line_quantities(pl)
    da = _aggregate_line_quantities(al)
    if not dp and not da:
        return False
    if set(dp.keys()) != set(da.keys()):
        return True
    for k in dp:
        if not math.isclose(dp[k], da[k], rel_tol=0, abs_tol=1e-6):
            return True
    return False


def _get_or_create_settings(company_id: str, db: Session) -> models.CompanySettings:
    from datetime import time
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if not s:
        s = models.CompanySettings(
            company_id=company_id,
            unit="個",
            tolerance_value=0,
            day_boundary_time=time(0, 0),
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _apply_user_classification(unit: models.WorkUnit, settings: models.CompanySettings) -> None:
    unreg, src = classify_leader(unit.user_id, settings.field_users or "")
    unit.is_unregistered_user = unreg
    unit.user_source = src


def _flow_and_diff_flags(unit: models.WorkUnit, settings: models.CompanySettings):
    """
    入力時に更新する異常フラグのみ（is_missing は含まない）。
    - is_invalid_flow: 着手なしで実績あり
    - is_diff_anomaly: 合計差・明細不一致・予告なし実績 等
    is_missing は「現在営業日より前」の行に対し missing_boundary でのみ更新する。
    """
    tol = int(settings.tolerance_value or 0)
    im = _norm_input_mode(settings)
    is_invalid_flow = unit.started_at is None and unit.actual_value is not None

    is_total_diff = False
    is_line_mismatch = False
    if unit.planned_value is not None and unit.actual_value is not None:
        dv = unit.diff_value
        if dv is None:
            dv = float(unit.actual_value) - float(unit.planned_value)
        is_total_diff = abs(dv) > tol
        is_line_mismatch = _planned_actual_line_mismatch(unit, im)

    is_no_forecast_but_actual = (
        unit.planned_value is None and unit.actual_value is not None
    )
    is_diff_anomaly = (
        is_total_diff or is_line_mismatch or is_no_forecast_but_actual
    )
    return is_invalid_flow, is_diff_anomaly


def _update_flags(unit: models.WorkUnit, settings: models.CompanySettings) -> None:
    """is_missing は更新しない（過去営業日の再計算のみ）。"""
    inv, diff_a = _flow_and_diff_flags(unit, settings)
    unit.is_invalid_flow = inv
    unit.is_diff_anomaly = diff_a


def _sync_work_status(
    unit: models.WorkUnit, settings: models.CompanySettings, db: Session
) -> None:
    """
    blue/normal のみ。closed / red は上書きしない。
    status 判定は is_missing / is_invalid_flow / is_diff_anomaly のみ（started_at 等は直接見ない）。
    is_missing は「現在営業日より前」の行だけ反映（当日は未確定のため無視）。
    """
    cur = (unit.status or "normal").strip().lower()
    if cur in ("closed", "red"):
        return
    current_biz = calc_business_date(datetime.utcnow(), settings, db)
    past = unit.business_date < current_biz
    missing_counts = past and bool(unit.is_missing)
    if missing_counts or unit.is_invalid_flow or unit.is_diff_anomaly:
        unit.status = "blue"
    else:
        unit.status = "normal"


def _status_for_response(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
    m: bool,
    inv: bool,
    diff_a: bool,
) -> str:
    """API の status。is_missing は過去営業日の行だけ考慮（当日は inv / diff_a のみ）。"""
    cur = (unit.status or "normal").strip().lower()
    if cur in ("closed", "red"):
        return cur
    current_biz = calc_business_date(datetime.utcnow(), settings, db)
    past = unit.business_date < current_biz
    if (past and m) or inv or diff_a:
        return "blue"
    return "normal"


def _unit_to_out(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
    prev_unit: Optional[models.WorkUnit] = None,
) -> dict:
    m = bool(unit.is_missing)
    inv, diff_a = _flow_and_diff_flags(unit, settings)
    im = _norm_input_mode(settings)
    plines = _planned_lines_for_response(unit, im)
    alines = _actual_lines_for_response(unit, im)
    prev_plines = _planned_lines_for_response(prev_unit, im) if prev_unit else []
    return {
        "id":                 unit.id,
        "company_id":         unit.company_id,
        "task_id":            unit.task_id,
        "process_id":         unit.process_id,
        "user_id":            unit.user_id,
        "business_date":      str(unit.business_date),
        "created_at":         unit.created_at.isoformat() if getattr(unit, "created_at", None) else None,
        "business_date_source": getattr(unit, "business_date_source", None),
        "business_date_debug": _parse_unit_business_date_debug(unit),
        "input_mode":         im,
        "planned_work_type":  unit.planned_work_type,
        "planned_work_label": unit.planned_work_label,
        "planned_item_name":  unit.planned_item_name,
        "planned_lines":      plines,
        "planned_value":      unit.planned_value,
        "started_at":         unit.started_at.isoformat() if unit.started_at else None,
        "actual_work_type":   unit.actual_work_type,
        "actual_work_label":  unit.actual_work_label,
        "actual_item_name":   unit.actual_item_name,
        "actual_lines":       alines,
        "actual_value":       unit.actual_value,
        "actual_at":          unit.actual_at.isoformat() if unit.actual_at else None,
        "pattern_a":          unit.pattern_a,
        "pattern_b":          unit.pattern_b,
        "status":             _status_for_response(unit, settings, db, m, inv, diff_a),
        "diff_value":         unit.diff_value,
        "is_missing":         m,
        "is_invalid_flow":    inv,
        "is_diff_anomaly":    diff_a,
        "is_unregistered_user": bool(unit.is_unregistered_user),
        "user_source":        unit.user_source or "master",
        "prev_planned_value": prev_unit.planned_value if prev_unit else None,
        "prev_planned_work_type": prev_unit.planned_work_type if prev_unit else None,
        "prev_planned_work_label": prev_unit.planned_work_label if prev_unit else None,
        "prev_planned_item_name": prev_unit.planned_item_name if prev_unit else None,
        "prev_planned_lines": prev_plines,
        "unit":               settings.unit or "個",
    }


def _parse_unit_business_date_debug(unit: models.WorkUnit):
    raw = getattr(unit, "business_date_debug_json", None)
    if not raw or not str(raw).strip():
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"parse_error": True, "raw": str(raw)[:500]}


def _find_prev_unit(company_id, task_id, process_id, user_id,
                    before_date, db: Session) -> Optional[models.WorkUnit]:
    return db.query(models.WorkUnit).filter(
        models.WorkUnit.company_id  == company_id,
        models.WorkUnit.task_id     == task_id,
        models.WorkUnit.process_id  == process_id,
        models.WorkUnit.user_id     == user_id,
        models.WorkUnit.business_date < before_date,
    ).order_by(models.WorkUnit.business_date.desc()).first()


# ─── エンドポイント ──────────────────────────────────────────

@router.get("/work/next-business-date", summary="次の営業日を返す（行は作らない）")
def get_next_business_date_only(
    company_id: str,
    current_business_date: str,
    db: Session = Depends(get_db),
):
    _get_or_create_settings(company_id, db)
    cur = date_type.fromisoformat(current_business_date)
    nxt = next_business_day(cur, company_id, db)
    return {"business_date": str(nxt)}


@router.post("/work", summary="今日の作業記録を取得または作成する")
def get_or_create_work(body: schemas.WorkUnitQuery, db: Session = Depends(get_db)):
    settings = _get_or_create_settings(body.company_id, db)
    if body.business_date:
        biz_date = date_type.fromisoformat(body.business_date)
        biz_debug = {
            "timezone": "Asia/Tokyo",
            "api": "POST /work",
            "client_provided_business_date": biz_date.isoformat(),
            "note": "リクエストの business_date をそのまま採用（サーバで JST 再計算なし）",
            "day_boundary_time_in_settings": settings.day_boundary_time.isoformat()
            if settings.day_boundary_time
            else None,
        }
        biz_source = "post_work_explicit"
    else:
        biz_date, biz_debug = calc_business_date_detailed(datetime.utcnow(), settings, db)
        biz_debug["api"] = "POST /work"
        biz_source = "post_work_auto"

    unit = db.query(models.WorkUnit).filter_by(
        company_id=body.company_id, task_id=body.task_id,
        process_id=body.process_id, user_id=body.user_id,
        business_date=biz_date,
    ).first()

    if unit is None:
        unit = models.WorkUnit(
            company_id=body.company_id, task_id=body.task_id,
            process_id=body.process_id, user_id=body.user_id,
            business_date=biz_date,
            status="normal",
        )
        unit.business_date_source = biz_source
        unit.business_date_debug_json = json.dumps(biz_debug, ensure_ascii=False)
        unit.created_at = datetime.utcnow()
        db.add(unit)
        db.flush()

    _update_flags(unit, settings)
    recompute_is_missing_for_past_business_dates(body.company_id, db)
    _sync_work_status(unit, settings, db)
    _apply_user_classification(unit, settings)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(body.company_id, body.task_id, body.process_id,
                                body.user_id, biz_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post("/work/next-day", summary="次の営業日を開始する（着手含む）")
def start_next_day(body: schemas.NextDayQuery, db: Session = Depends(get_db)):
    settings     = _get_or_create_settings(body.company_id, db)
    current_date = date_type.fromisoformat(body.current_business_date)
    next_date, next_dbg = next_business_day_detailed(current_date, body.company_id, db)
    next_dbg["api"] = "POST /work/next-day"

    unit = db.query(models.WorkUnit).filter_by(
        company_id=body.company_id, task_id=body.task_id,
        process_id=body.process_id, user_id=body.user_id,
        business_date=next_date,
    ).first()

    if unit is None:
        unit = models.WorkUnit(
            company_id=body.company_id, task_id=body.task_id,
            process_id=body.process_id, user_id=body.user_id,
            business_date=next_date,
            status="normal",
        )
        unit.business_date_source = "post_work_next_day"
        unit.business_date_debug_json = json.dumps(next_dbg, ensure_ascii=False)
        unit.created_at = datetime.utcnow()
        db.add(unit)
        db.flush()

    _update_flags(unit, settings)
    recompute_is_missing_for_past_business_dates(body.company_id, db)
    _sync_work_status(unit, settings, db)
    _apply_user_classification(unit, settings)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(body.company_id, body.task_id, body.process_id,
                                body.user_id, next_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post("/work/{unit_id}/close", summary="【事務】作業記録を承認・完了（status=closed）")
def approve_close_work(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_or_create_settings(unit.company_id, db)
    unit.status = "closed"
    recompute_is_missing_for_past_business_dates(unit.company_id, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post("/work/{unit_id}/start", summary="着手を記録する")
def mark_started(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_or_create_settings(unit.company_id, db)
    if unit.started_at is None:
        unit.started_at = datetime.utcnow()
    _update_flags(unit, settings)
    recompute_is_missing_for_past_business_dates(unit.company_id, db)
    _sync_work_status(unit, settings, db)
    _apply_user_classification(unit, settings)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post("/work/{unit_id}/actual", summary="実績を記録する")
def save_actual(unit_id: int, body: schemas.ActualIn, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_or_create_settings(unit.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    if "lines" in patch:
        raw_lines = body.lines if body.lines is not None else []
        lines, err = _strict_lines_from_body(list(raw_lines))
        if err:
            raise HTTPException(status_code=422, detail=err)
        unit.actual_lines_json = _lines_json_dumps(lines) if lines else None
        if lines:
            unit.actual_value = sum(x["value"] for x in lines)
            if im == "logistics":
                unit.actual_work_label = _join_line_labels(lines)
                unit.actual_work_type = None
                unit.actual_item_name = None
            else:
                unit.actual_item_name = _join_line_labels(lines)
                unit.actual_work_label = None
                unit.actual_work_type = None
        else:
            unit.actual_value = None
            unit.actual_lines_json = None
            unit.actual_item_name = None
            unit.actual_work_label = None
            unit.actual_work_type = None
    else:
        unit.actual_lines_json = None
        unit.actual_value = body.actual_value
        unit.actual_work_type = _opt_str(body.actual_work_type)
        unit.actual_work_label = _opt_str(body.actual_work_label)
        unit.actual_item_name = _opt_str(body.actual_item_name)

    unit.actual_at = datetime.utcnow()

    if "pattern_a" in patch:
        unit.pattern_a = patch["pattern_a"]
    if "pattern_b" in patch:
        unit.pattern_b = patch["pattern_b"]

    if unit.planned_value is not None and unit.actual_value is not None:
        unit.diff_value = unit.actual_value - unit.planned_value

    _update_flags(unit, settings)
    recompute_is_missing_for_past_business_dates(unit.company_id, db)
    _sync_work_status(unit, settings, db)
    _apply_user_classification(unit, settings)
    _touch_updated(unit)
    db.commit()

    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    out = _unit_to_out(unit, settings, db, prev_unit)
    out["next_business_date"] = str(next_business_day(unit.business_date, unit.company_id, db))
    return out


@router.post("/work/{unit_id}/planned", summary="予告を記録する")
def save_planned(unit_id: int, body: schemas.PlannedIn, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_or_create_settings(unit.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    if "lines" in patch:
        raw_lines = body.lines if body.lines is not None else []
        lines, err = _strict_lines_from_body(list(raw_lines))
        if err:
            raise HTTPException(status_code=422, detail=err)
        unit.planned_lines_json = _lines_json_dumps(lines) if lines else None
        if lines:
            unit.planned_value = sum(x["value"] for x in lines)
            if im == "logistics":
                unit.planned_work_label = _join_line_labels(lines)
                unit.planned_work_type = None
                unit.planned_item_name = None
            else:
                unit.planned_item_name = _join_line_labels(lines)
                unit.planned_work_label = None
                unit.planned_work_type = None
        else:
            unit.planned_value = None
            unit.planned_lines_json = None
            unit.planned_item_name = None
            unit.planned_work_label = None
            unit.planned_work_type = None
    else:
        unit.planned_lines_json = None
        unit.planned_value = body.planned_value
        unit.planned_work_type = _opt_str(body.planned_work_type)
        unit.planned_work_label = _opt_str(body.planned_work_label)
        unit.planned_item_name = _opt_str(body.planned_item_name)

    if unit.planned_value is not None and unit.actual_value is not None:
        unit.diff_value = unit.actual_value - unit.planned_value

    _update_flags(unit, settings)
    recompute_is_missing_for_past_business_dates(unit.company_id, db)
    _sync_work_status(unit, settings, db)
    _apply_user_classification(unit, settings)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post(
    "/work/recalc-missing-boundary",
    summary="過去営業日の is_missing 再計算（cron・境界後のバッチ用）",
)
def recalc_missing_boundary(
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    本番では cron 等から定期実行する想定の本線エンドポイント。
    company_id 省略時は全企業。営業日が現在より前の行の is_missing を更新する（closed/red は status は変えない）。
    """
    if company_id and str(company_id).strip():
        cid = str(company_id).strip()
        _get_or_create_settings(cid, db)
        n = recompute_is_missing_for_past_business_dates(cid, db)
        db.commit()
        return {"ok": True, "company_id": cid, "units_scanned": n}

    rows = db.query(models.CompanySettings.company_id).all()
    total = 0
    for (cid,) in rows:
        total += recompute_is_missing_for_past_business_dates(cid, db)
    db.commit()
    return {"ok": True, "company_id": None, "units_scanned": total}


@router.post(
    "/work/debug-reset",
    summary="【デバッグ】work_unit / work_anomaly を全削除（ローカル検証専用）",
)
def debug_reset(db: Session = Depends(get_db)):
    """
    テストデータ混在を防ぐための履歴クリア。本番では使用しない。
    FK がある場合に備え work_anomaly を先に削除する。
    """
    bind = db.get_bind()
    insp = inspect(bind)
    deleted_anomaly = 0
    if insp.has_table("work_anomaly"):
        r = db.execute(text("DELETE FROM work_anomaly"))
        deleted_anomaly = r.rowcount if r.rowcount is not None else 0
    r2 = db.execute(text("DELETE FROM work_unit"))
    deleted_unit = r2.rowcount if r2.rowcount is not None else 0
    db.commit()
    return {
        "ok": True,
        "deleted_work_anomaly_rows": deleted_anomaly,
        "deleted_work_unit_rows": deleted_unit,
    }


@router.post(
    "/work/debug-set-business-date",
    summary="【デバッグ】指定レコードの business_date を手動変更（本番非推奨）",
)
def debug_set_business_date(
    body: schemas.DebugSetBusinessDateIn,
    db: Session = Depends(get_db),
):
    """
    未入力・営業日跨ぎのテスト用。変更後に is_missing 再計算（当社・他行含む）を実行する。
    """
    unit = db.get(models.WorkUnit, body.id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    try:
        new_d = date_type.fromisoformat(body.business_date.strip())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="business_date は YYYY-MM-DD 形式で指定してください",
        )

    dup = (
        db.query(models.WorkUnit)
        .filter(
            models.WorkUnit.company_id == unit.company_id,
            models.WorkUnit.task_id == unit.task_id,
            models.WorkUnit.process_id == unit.process_id,
            models.WorkUnit.user_id == unit.user_id,
            models.WorkUnit.business_date == new_d,
            models.WorkUnit.id != unit.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(
            status_code=409,
            detail="同一キーでその営業日の別レコードが既にあります（debug）",
        )

    unit.business_date = new_d
    settings = _get_or_create_settings(unit.company_id, db)
    current_biz = calc_business_date(datetime.utcnow(), settings, db)
    if unit.business_date < current_biz:
        unit.is_missing = (
            unit.planned_value is None
            or unit.actual_value is None
            or unit.started_at is None
        )
    else:
        unit.is_missing = False

    st = (unit.status or "normal").strip().lower()
    if st not in ("closed", "red"):
        _sync_work_status(unit, settings, db)

    recompute_is_missing_for_past_business_dates(unit.company_id, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(
        unit.company_id,
        unit.task_id,
        unit.process_id,
        unit.user_id,
        unit.business_date,
        db,
    )
    return _unit_to_out(unit, settings, db, prev_unit)


@router.get("/work/list", summary="作業記録の一覧を取得する")
def list_work(company_id: str, db: Session = Depends(get_db)):
    settings = _get_or_create_settings(company_id, db)
    # 暫定: デバッグ一覧を開いたときに過去営業日の is_missing を揃える（副作用で commit）。
    # 本線は cron 等から POST /work/recalc-missing-boundary のみで再計算し、本 GET は読み取りのみに寄せる想定。
    recompute_is_missing_for_past_business_dates(company_id, db)
    db.commit()
    sort_key = func.coalesce(models.WorkUnit.updated_at, models.WorkUnit.created_at)
    units = (
        db.query(models.WorkUnit)
        .filter_by(company_id=company_id)
        .order_by(sort_key.desc().nulls_last(), models.WorkUnit.id.desc())
        .limit(200)
        .all()
    )
    return [_unit_to_out(u, settings, db) for u in units]
