import hashlib
import json
import logging
import math
import uuid
from datetime import datetime, date as date_type, time
from typing import Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.services.test_clock import reference_utc_now
from app.services.work_unit_guard import is_closed, raise_if_closed
from app.services.status_history import (
    append_work_unit_status_history_if_changed,
    norm_work_unit_status,
)
from app.services.judgement_promote import (
    compute_red_deadline_jst,
    incomplete_implies_status_blue,
    next_work_end_boundary_jst,
    promote_blue_to_red_after_judgement,
    reference_now_jst,
)
from app.services.package_rules import is_phase2_enabled
from app.services.article7_deviation import is_actual_deviation_from_article7
from app.services.product_master import (
    enrich_actual_lines_product_codes,
    ensure_product_master_labels,
)

router = APIRouter(tags=["作業記録"])
logger = logging.getLogger(__name__)


def _touch_updated(unit: models.WorkUnit) -> None:
    """一覧の並び（updated_at desc）用。保存直前に呼ぶ。"""
    unit.updated_at = datetime.utcnow()


def _flush_then_recompute_past_missing(db: Session, company_id: str) -> int:
    """Session は autoflush=False のため、過去営業日の再計算クエリの前に未反映の変更を DB に同期する。"""
    db.flush()
    return recompute_is_missing_for_past_business_dates(company_id, db)


# ─── ヘルパー ────────────────────────────────────────────────

def _opt_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def _legacy_planned_line_id(unit_id: int, label: str, value: float) -> str:
    """レガシー1行予告（JSON なし）用の安定 line_id（GET のたびに同じ値）。"""
    h = hashlib.sha256(f"{unit_id}\0{label}\0{value}".encode("utf-8")).hexdigest()[:26]
    return f"mo-legacy-{h}"


def _norm_due_date(raw: Optional[str]) -> Optional[str]:
    """YYYY-MM-DD のみ受理。不正なら None。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        d = date_type.fromisoformat(s)
    except ValueError:
        return None
    return d.isoformat()


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
            row = {"label": lb, "value": fv}
            pc_line = str(it.get("product_code", "")).strip()
            if pc_line:
                row["product_code"] = pc_line
            lid = it.get("line_id")
            if lid is not None and str(lid).strip():
                row["line_id"] = str(lid).strip()
            dd = it.get("due_date")
            if dd is not None and str(dd).strip():
                nd = _norm_due_date(str(dd).strip())
                if nd:
                    row["due_date"] = nd
            out.append(row)
    return out


def _assign_missing_line_ids_mutate(rows: List[dict]) -> bool:
    """行に line_id が無ければ付与。重複は空き UUID で回避。変更があれば True。"""
    changed = False
    seen: Set[str] = set()
    for r in rows:
        lid = str(r.get("line_id") or "").strip()
        if lid:
            seen.add(lid)
    for r in rows:
        lid = str(r.get("line_id") or "").strip()
        if lid:
            continue
        nid = str(uuid.uuid4())
        while nid in seen:
            nid = str(uuid.uuid4())
        r["line_id"] = nid
        seen.add(nid)
        changed = True
    return changed


def _backfill_stored_planned_line_ids(unit: models.WorkUnit) -> bool:
    """Ensure each stored planned JSON row has line_id; persist when missing."""
    raw = getattr(unit, "planned_lines_json", None)
    rows = _parse_lines_json(raw)
    if not rows:
        return False
    if _assign_missing_line_ids_mutate(rows):
        unit.planned_lines_json = _lines_json_dumps(rows)
        return True
    return False


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
    *,
    include_due_date: bool = False,
    include_line_id: bool = False,
    include_product_code: bool = False,
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
        dct: dict = {"label": lb, "value": fv}
        if include_product_code:
            raw_pc = getattr(row, "product_code", None)
            if raw_pc is not None and str(raw_pc).strip():
                dct["product_code"] = str(raw_pc).strip()
        if include_line_id:
            raw_lid = getattr(row, "line_id", None)
            if raw_lid is not None and str(raw_lid).strip():
                dct["line_id"] = str(raw_lid).strip()
        if include_due_date:
            if "due_date" in row.model_fields_set:
                raw_due = row.due_date
                if raw_due is None or not str(raw_due).strip():
                    dct["_due_cleared"] = True
                else:
                    nd = _norm_due_date(str(raw_due).strip())
                    if nd is None:
                        return None, "due_date は YYYY-MM-DD で指定してください"
                    dct["due_date"] = nd
        complete.append(dct)
    if include_line_id and complete:
        seen: Set[str] = set()
        for dct in complete:
            lid = str(dct.get("line_id") or "").strip()
            if lid:
                if lid in seen:
                    return None, "line_id が重複しています"
                seen.add(lid)
        for dct in complete:
            if not str(dct.get("line_id") or "").strip():
                nid = str(uuid.uuid4())
                while nid in seen:
                    nid = str(uuid.uuid4())
                dct["line_id"] = nid
                seen.add(nid)
    return complete, None


def _merge_due_from_previous(new_lines: List[dict], old_lines: Optional[List[dict]]) -> None:
    """クライアントが due_date を省略したとき、同一 line_id の直前の行から引き��ぐ。"""
    if not old_lines:
        return
    key_due: Dict[str, str] = {}
    for o in old_lines:
        lid = str(o.get("line_id") or "").strip()
        if not lid:
            continue
        dd = o.get("due_date")
        if not dd or not str(dd).strip():
            continue
        nd = _norm_due_date(str(dd).strip())
        if nd:
            key_due[lid] = nd
    for nl in new_lines:
        if nl.get("due_date"):
            nl.pop("_due_cleared", None)
            continue
        if nl.pop("_due_cleared", False):
            nl.pop("due_date", None)
            continue
        lid = str(nl.get("line_id") or "").strip()
        if lid and lid in key_due:
            nl["due_date"] = key_due[lid]


def _planned_lines_for_response(unit: models.WorkUnit, im: str) -> List[dict]:
    parsed = _parse_lines_json(getattr(unit, "planned_lines_json", None))
    if parsed:
        return parsed
    v = unit.planned_value
    if v is None or not math.isfinite(float(v)):
        return []
    fv = float(v)
    uid = int(unit.id)
    if im == "logistics":
        lab = _opt_str(unit.planned_work_label) or _opt_str(unit.planned_work_type)
        if not lab:
            return []
        return [{"label": lab, "value": fv, "line_id": _legacy_planned_line_id(uid, lab, fv)}]
    n = (unit.planned_item_name or "").strip()
    if not n:
        return []
    return [{"label": n, "value": fv, "line_id": _legacy_planned_line_id(uid, n, fv)}]


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


def _numeric_nonzero(v) -> bool:
    """None / 非数 / 0 は false（文字列 "0" も float で 0 扱い）。"""
    if v is None:
        return False
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(fv):
        return False
    return fv != 0


def _has_planned_nonzero_from_rel_lines(unit: models.WorkUnit) -> bool:
    """現場v2の WorkUnitLine（line_type=planned）。value が実数かつ 0 でないときのみ予告あり。"""
    rel = getattr(unit, "lines", None) or []
    for ln in rel:
        if getattr(ln, "line_type", None) != "planned":
            continue
        if _numeric_nonzero(getattr(ln, "value", None)):
            return True
    return False


def _has_planned_nonzero(unit: models.WorkUnit, settings: models.CompanySettings) -> bool:
    """
    A* 用「予告あり」: 次のいずれかで True
    - planned_lines_json にラベル付きかつ数量≠0 の行がある
    - planned_value が実数かつ≠0（NULL は.false）
    - 子テーブル planned 行に quantity≠0 がある（v2）

    None / "" / 0 / "0" / 数量なし行のみ / 空配列 → false。
    JSON に行があるが 0 ばかりのときも planned_value・子行をフォールバックで見る。
    """
    parsed = _parse_lines_json(getattr(unit, "planned_lines_json", None))
    if parsed:
        json_hit = False
        for it in parsed:
            if not isinstance(it, dict):
                continue
            lb = str(it.get("label", "")).strip()
            if not lb:
                continue
            raw = it.get("value")
            if raw is not None and raw != "" and _numeric_nonzero(raw):
                json_hit = True
                break
        if json_hit:
            return True
    if _numeric_nonzero(getattr(unit, "planned_value", None)):
        return True
    return _has_planned_nonzero_from_rel_lines(unit)


def _has_meaningful_actual(unit: models.WorkUnit, settings: models.CompanySettings) -> bool:
    im = _norm_input_mode(settings)
    if _actual_lines_for_response(unit, im):
        return True
    v = unit.actual_value
    return v is not None and math.isfinite(float(v))


def _has_actual_signal(unit: models.WorkUnit, settings: models.CompanySettings) -> bool:
    """実績あり: actual_at または数量・明細（着手/流れ判定もここに合わせる）。"""
    if getattr(unit, "actual_at", None) is not None:
        return True
    return _has_meaningful_actual(unit, settings)


def _get_or_create_settings(company_id: str, db: Session) -> models.CompanySettings:
    from datetime import time
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if not s:
        s = models.CompanySettings(
            company_id=company_id,
            unit="個",
            tolerance_value=0,
            day_boundary_time=time(0, 0),
            package_code="A",
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _apply_user_classification(unit: models.WorkUnit, settings: models.CompanySettings) -> None:
    unreg, src = classify_leader(unit.user_id, settings.field_users or "")
    unit.is_unregistered_user = unreg
    unit.user_source = src


def _apply_minimal_judgement(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    *,
    db: Optional[Session] = None,
    force_status: Optional[str] = None,
) -> None:
    """
    第5条フェーズ1（最小構成）: system_pattern / status（終了以外）を書く責務はこの関数のみ。

    登録済:
      A*（プロセス不備）: 予告なし+着手 / 予告なし+実績 / 着手なし+実績
      B*（数値乖離・pattern 専用）: 予告あり+実績ありで |actual−planned| > tolerance のみ。
        予告なしで実績だけ進んだケースは A* のみ（結果不備の青判定は内部の sys_b で扱うが B* ラベルは付けない）。
    status（青）:
      順序違反・結果不備（予告なし実績含む）・数値乖離: sys_a または sys_b に該当するとき即時 blue
      未完了（予告あり・実績なし）: 翌営業日の work_end_time を跨いだ後のみ blue
    未登録: pattern 空・blue。
    上記いずれでもない（登録済）: pattern 空・normal。

    保存直後に _recompute から呼ぶ。GET /work/list でも時刻依存の青を反映するため再計算する。
    force_status が closed/red のときは終了のみ（pattern は変更しない）。

    status が実際に変わったときだけ work_unit_status_history に追記（db があるとき）。
    force_status=closed は trigger_type=office、それ以外の自動判定は system。
    """
    status_before = norm_work_unit_status(unit.status)
    trigger = "office" if force_status == "closed" else "system"
    try:
        if force_status in ("closed", "red"):
            unit.status = force_status
            return

        # 完了済みは再判定で status / pattern を上書きしない（closed 後は戻せない）
        if is_closed(unit):
            return

        hp = _has_planned_nonzero(unit, settings)
        hs = unit.started_at is not None
        ha = _has_actual_signal(unit, settings)
        ha_meaningful = _has_meaningful_actual(unit, settings)

        unreg = bool(getattr(unit, "is_unregistered_user", False))
        if unreg:
            unit.system_pattern = ""
            unit.status = "blue"
            print(
                "[measureos.pattern_debug] SET system_pattern:",
                repr(unit.system_pattern),
                "unit_id=",
                getattr(unit, "id", None),
                "reason=unreg",
                flush=True,
            )
            logger.warning(
                "[measureos.pattern_debug] SET system_pattern=%r unit_id=%s reason=unreg status=%r",
                unit.system_pattern,
                getattr(unit, "id", None),
                unit.status,
            )
            logger.info(
                "[measureos.judge] unit_id=%s company_id=%r unreg=True -> pattern='' status=blue",
                getattr(unit, "id", None),
                getattr(unit, "company_id", None),
            )
            return

        sys_a = ((not hp) and (hs or ha)) or ((not hs) and ha)
        b_no_planned_actual = (not hp) and ha
        b_tolerance = False
        if hp and ha:
            tol = int(settings.tolerance_value or 0)
            try:
                dv = unit.diff_value
                if dv is None:
                    dv = float(unit.actual_value) - float(unit.planned_value)
                b_tolerance = abs(dv) > tol
            except (TypeError, ValueError):
                b_tolerance = False
        sys_b = b_no_planned_actual or b_tolerance

        parts: List[str] = []
        if sys_a:
            parts.append("A*")
        # B* は is_diff_anomaly と同義（許容超過のみ）。予告なし実績は A* で表す。
        if b_tolerance:
            parts.append("B*")
        if bool(getattr(unit, "is_article7_deviation", False)):
            parts.append("7条逸脱")
        computed_pattern = ",".join(parts)
        unit.system_pattern = computed_pattern
        print(
            "[measureos.pattern_debug] SET system_pattern:",
            repr(computed_pattern),
            "unit_id=",
            getattr(unit, "id", None),
            "sys_a=",
            sys_a,
            "sys_b=",
            sys_b,
            flush=True,
        )
        logger.warning(
            "[measureos.pattern_debug] SET system_pattern=%r unit_id=%s sys_a=%s sys_b=%s (registered)",
            computed_pattern,
            getattr(unit, "id", None),
            sys_a,
            sys_b,
        )

        order_or_tolerance_blue = sys_a or sys_b
        incomplete_blue = incomplete_implies_status_blue(
            has_planned_nonzero=hp,
            has_meaningful_actual=ha_meaningful,
            business_date=unit.business_date,
            company_id=unit.company_id,
            settings=settings,
            db=db,
        )
        if order_or_tolerance_blue or incomplete_blue:
            unit.status = "blue"
        else:
            unit.status = "normal"

        wet = settings.work_end_time or time(17, 0)
        now_jst = reference_now_jst() if db is not None else None
        boundary_jst = (
            next_work_end_boundary_jst(unit.business_date, wet, unit.company_id, db)
            if db is not None
            else None
        )
        logger.info(
            "[measureos.judge.detail] unit_id=%s company_id=%r hp=%s hs=%s ha=%s ha_meaningful=%s "
            "now_jst=%s next_work_end_boundary_jst=%s "
            "order_or_tolerance_blue=%s incomplete_blue=%s status=%r",
            getattr(unit, "id", None),
            getattr(unit, "company_id", None),
            hp,
            hs,
            ha,
            ha_meaningful,
            now_jst.isoformat() if now_jst else None,
            boundary_jst.isoformat() if boundary_jst else None,
            order_or_tolerance_blue,
            incomplete_blue,
            unit.status,
        )

        logger.info(
            "[measureos.judge] unit_id=%s company_id=%r hp=%s hs=%s ha=%s sys_a=%s sys_b=%r "
            "is_missing=%s incomplete_blue=%s pattern=%r status=%r",
            getattr(unit, "id", None),
            getattr(unit, "company_id", None),
            hp,
            hs,
            ha,
            sys_a,
            sys_b,
            bool(getattr(unit, "is_missing", False)),
            incomplete_blue,
            unit.system_pattern,
            unit.status,
        )
    finally:
        if db is not None:
            append_work_unit_status_history_if_changed(db, unit, status_before, trigger)


def _audit_x_save(unit: models.WorkUnit, settings: models.CompanySettings, route: str, phase: str) -> None:
    """company_id が x の行のみ、保存検証用ログ（説明用コメントなし）。"""
    if unit.company_id != "x":
        return
    hp = _has_planned_nonzero(unit, settings)
    hs = unit.started_at is not None
    ha = _has_actual_signal(unit, settings)
    logger.warning(
        "[measureos.x_audit] route=%s phase=%s unit_id=%s has_planned=%s has_started=%s "
        "has_actual=%s system_pattern=%r status=%r is_unregistered=%s",
        route,
        phase,
        unit.id,
        hp,
        hs,
        ha,
        getattr(unit, "system_pattern", None),
        unit.status,
        bool(getattr(unit, "is_unregistered_user", False)),
    )


def _update_is_missing_summary(
    unit: models.WorkUnit, settings: models.CompanySettings, db: Session
) -> None:
    """
    未入力（is_missing）の要約。
    - 現行営業日かつ status が normal: 予告だけ等・未完了でもまだ立てない（境界・再判定で blue 後に同期）。
    - 過去営業日かつ normal: 欠けがあれば true（事後照会）。
    - blue: missing_boundary と同式（着手だけ即時 blue の T2 等と整合）。
    """
    cur = (unit.status or "").strip().lower()
    if cur in ("closed", "red"):
        return

    def _missing_triplet() -> bool:
        return (
            unit.planned_value is None
            or unit.actual_value is None
            or unit.started_at is None
        )

    ref = reference_utc_now()
    current_biz = calc_business_date(ref, settings, db)
    is_past = unit.business_date < current_biz

    if cur == "normal":
        if not is_past:
            unit.is_missing = False
            return
        unit.is_missing = _missing_triplet()
        return

    if cur == "blue":
        unit.is_missing = _missing_triplet()
        return

    unit.is_missing = _missing_triplet()


def _update_flags(unit: models.WorkUnit, settings: models.CompanySettings) -> None:
    """
    補助フラグ。
    - is_diff_anomaly: 数値乖離のみ（予告・実績が揃い |actual−planned| > tolerance）。
      system_pattern の B* は「予告なし+実績」も含むが、それは結果不備であり数値乖離ではない。
    - is_invalid_flow: A*（プロセス不備）または 実績あり・着手なし
    """
    segs = [x.strip() for x in (unit.system_pattern or "").split(",") if x.strip()]
    hp = _has_planned_nonzero(unit, settings)
    ha = _has_actual_signal(unit, settings)
    b_tolerance = False
    if hp and ha:
        tol = int(settings.tolerance_value or 0)
        try:
            dv = unit.diff_value
            if dv is None:
                dv = float(unit.actual_value) - float(unit.planned_value)
            b_tolerance = abs(dv) > tol
        except (TypeError, ValueError):
            b_tolerance = False
    unit.is_diff_anomaly = b_tolerance
    # 順序不備: A*（プロセス不備）に該当、または 実績あり・着手なし
    unit.is_invalid_flow = bool(
        "A*" in segs
        or (_has_actual_signal(unit, settings) and unit.started_at is None)
    )


def _sync_status_blue_from_derived_flags(
    unit: models.WorkUnit,
    db: Session,
) -> None:
    """
    is_missing / is_invalid_flow / is_diff_anomaly / is_unregistered_user と status を整合させる。
    _apply_minimal_judgement のみでは normal のまま残り得るが、派生フラグが異常なら blue にする。
    一覧取得・保存・テスト再判定はすべて _recompute_unit_derived 経由でここを通す。
    """
    st = (unit.status or "").strip().lower()
    if st in ("closed", "red", "blue"):
        return
    if not (
        bool(unit.is_missing)
        or bool(getattr(unit, "is_invalid_flow", False))
        or bool(getattr(unit, "is_diff_anomaly", False))
        or bool(getattr(unit, "is_unregistered_user", False))
        or bool(getattr(unit, "is_deviation", False))
        or bool(getattr(unit, "is_article7_deviation", False))
    ):
        return
    before = norm_work_unit_status(unit.status)
    unit.status = "blue"
    append_work_unit_status_history_if_changed(db, unit, before, "system")


def _sync_anomaly_started_at(unit: models.WorkUnit) -> None:
    """
    status が normal のときは異常開始時刻をクリア（予告だけ保存直後の整合）。
    blue 等では従来どおり初回のみセット。
    """
    st = (unit.status or "").strip().lower()
    if st == "normal":
        unit.anomaly_started_at = None
        return
    _maybe_set_anomaly_started_at(unit)


def _maybe_set_anomaly_started_at(unit: models.WorkUnit) -> None:
    """
    異常が初めて立った時刻（1回のみ）。既存値は上書きしない。
    ・status が blue、または is_missing / is_invalid_flow / is_diff_anomaly /
    is_unregistered_user のいずれかが真のときに初回セット。
    red 化・closed では値を消さない（再計算で terminal の行はここに来ない）。
    """
    if getattr(unit, "anomaly_started_at", None) is not None:
        return
    st = (unit.status or "").strip().lower()
    if (
        st == "blue"
        or bool(unit.is_missing)
        or bool(unit.is_invalid_flow)
        or bool(unit.is_diff_anomaly)
        or bool(getattr(unit, "is_unregistered_user", False))
        or bool(getattr(unit, "is_deviation", False))
        or bool(getattr(unit, "is_article7_deviation", False))
    ):
        unit.anomaly_started_at = datetime.utcnow()


def _recompute_unit_derived(
    unit: models.WorkUnit, settings: models.CompanySettings, db: Session
) -> None:
    """保存直後: 班長判定 → _apply_minimal_judgement → 補助フラグのみ。"""
    cur = (unit.status or "").strip().lower()
    if cur in ("closed", "red"):
        logger.info(
            "[measureos.judge] recompute_skip unit_id=%s reason=terminal_status=%r",
            getattr(unit, "id", None),
            cur or None,
        )
        return
    logger.info(
        "[measureos.judge] recompute_enter unit_id=%s company_id=%r",
        getattr(unit, "id", None),
        getattr(unit, "company_id", None),
    )
    _apply_user_classification(unit, settings)
    _apply_minimal_judgement(unit, settings, db=db)
    _update_is_missing_summary(unit, settings, db)
    _update_flags(unit, settings)
    _sync_status_blue_from_derived_flags(unit, db)
    _sync_anomaly_started_at(unit)


def _status_from_db(unit: models.WorkUnit) -> str:
    s = (unit.status or "").strip().lower()
    if s in ("closed", "red", "blue"):
        return s
    return "normal"


def _unit_to_out(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
    prev_unit: Optional[models.WorkUnit] = None,
) -> dict:
    if _backfill_stored_planned_line_ids(unit):
        _touch_updated(unit)
    if prev_unit is not None and _backfill_stored_planned_line_ids(prev_unit):
        _touch_updated(prev_unit)
    m = bool(unit.is_missing)
    im = _norm_input_mode(settings)
    plines = _planned_lines_for_response(unit, im)
    alines = _actual_lines_for_response(unit, im)
    prev_plines = _planned_lines_for_response(prev_unit, im) if prev_unit else []
    st_out = _status_from_db(unit)
    jt = settings.judgement_time or time(13, 0)
    judgement_red_deadline_at = None
    if st_out == "blue" and is_phase2_enabled(settings):
        judgement_red_deadline_at = compute_red_deadline_jst(
            unit.business_date, jt, unit.company_id, db
        ).isoformat()

    deviation_reason_out = str(getattr(unit, "deviation_reason", None) or "").strip()
    deviation_reason_out = deviation_reason_out or None

    return {
        "id":                 unit.id,
        "company_id":         unit.company_id,
        "task_id":            unit.task_id,
        "process_id":         unit.process_id,
        "user_id":            unit.user_id,
        "business_date":      str(unit.business_date),
        "planned_at":         unit.planned_at.isoformat() if getattr(unit, "planned_at", None) else None,
        "created_at":         unit.created_at.isoformat() if getattr(unit, "created_at", None) else None,
        "input_source":       getattr(unit, "input_source", None) or None,
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
        "user_pattern":       getattr(unit, "user_pattern", None) or None,
        "system_pattern":     getattr(unit, "system_pattern", None) or "",
        "status":             st_out,
        "judgement_red_deadline_at": judgement_red_deadline_at,
        "diff_value":         unit.diff_value,
        "is_missing":         m,
        "is_invalid_flow":    bool(getattr(unit, "is_invalid_flow", False)),
        "is_diff_anomaly":    bool(getattr(unit, "is_diff_anomaly", False)),
        "anomaly_started_at": unit.anomaly_started_at.isoformat()
        if getattr(unit, "anomaly_started_at", None)
        else None,
        "is_unregistered_user": bool(unit.is_unregistered_user),
        "user_source":        unit.user_source or "master",
        "is_deviation":       bool(getattr(unit, "is_deviation", False)),
        "is_article7_deviation": bool(getattr(unit, "is_article7_deviation", False)),
        "deviation_reason":   deviation_reason_out,
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
    logger.warning(
        "[measureos.work.hook] POST /work company_id=%r task_id=%r process_id=%r user_id=%r business_date=%r",
        body.company_id,
        body.task_id,
        body.process_id,
        body.user_id,
        body.business_date,
    )
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
        biz_date, biz_debug = calc_business_date_detailed(reference_utc_now(), settings, db)
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
        )
        unit.business_date_source = biz_source
        unit.business_date_debug_json = json.dumps(biz_debug, ensure_ascii=False)
        unit.created_at = datetime.utcnow()
        db.add(unit)
        db.flush()
    else:
        raise_if_closed(unit)

    _flush_then_recompute_past_missing(db, body.company_id)
    _recompute_unit_derived(unit, settings, db)
    _audit_x_save(unit, settings, "POST /work", "pre_commit")
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    _audit_x_save(unit, settings, "POST /work", "post_commit")
    logger.warning(
        "[measureos.work.hook] POST /work committed unit_id=%s company_id=%r business_date=%s has_actual_at=%s has_started_at=%s",
        unit.id,
        unit.company_id,
        unit.business_date,
        unit.actual_at is not None,
        unit.started_at is not None,
    )

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
        )
        unit.business_date_source = "post_work_next_day"
        unit.business_date_debug_json = json.dumps(next_dbg, ensure_ascii=False)
        unit.created_at = datetime.utcnow()
        db.add(unit)
        db.flush()
    else:
        raise_if_closed(unit)

    _flush_then_recompute_past_missing(db, body.company_id)
    _recompute_unit_derived(unit, settings, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(body.company_id, body.task_id, body.process_id,
                                body.user_id, next_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.get(
    "/work/{unit_id}/status-history",
    response_model=List[schemas.WorkUnitStatusHistoryItem],
    summary="status 変化履歴（新しい順・読み取り専用）",
)
def get_work_unit_status_history(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    rows = (
        db.query(models.WorkUnitStatusHistory)
        .filter(models.WorkUnitStatusHistory.work_unit_id == unit_id)
        .order_by(models.WorkUnitStatusHistory.changed_at.desc())
        .all()
    )
    out: List[schemas.WorkUnitStatusHistoryItem] = []
    for r in rows:
        out.append(
            schemas.WorkUnitStatusHistoryItem(
                id=r.id,
                from_status=r.from_status,
                to_status=r.to_status,
                changed_at=r.changed_at.isoformat() if r.changed_at else None,
                trigger_type=r.trigger_type,
            )
        )
    return out


@router.post("/work/{unit_id}/close", summary="【事務】作業記録を承認・完了（status=closed）")
def approve_close_work(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    settings = _get_or_create_settings(unit.company_id, db)
    if is_closed(unit):
        prev_unit = _find_prev_unit(
            unit.company_id, unit.task_id, unit.process_id,
            unit.user_id, unit.business_date, db,
        )
        return _unit_to_out(unit, settings, db, prev_unit)
    _apply_minimal_judgement(unit, settings, db=db, force_status="closed")
    _flush_then_recompute_past_missing(db, unit.company_id)
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
    raise_if_closed(unit)
    settings = _get_or_create_settings(unit.company_id, db)
    if unit.started_at is None:
        unit.started_at = datetime.utcnow()
    _flush_then_recompute_past_missing(db, unit.company_id)
    _recompute_unit_derived(unit, settings, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post("/work/{unit_id}/actual", summary="実績を記録する")
def save_actual(unit_id: int, body: schemas.ActualIn, db: Session = Depends(get_db)):
    patch_preview = body.model_dump(exclude_unset=True)
    logger.warning(
        "[measureos.work.hook] POST /work/%s/actual body_keys=%s lines_in_body=%s",
        unit_id,
        sorted(patch_preview.keys()),
        "lines" in patch_preview,
    )
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        logger.warning(
            "[measureos.work.hook] POST /work/%s/actual — no row (404)",
            unit_id,
        )
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    raise_if_closed(unit)
    settings = _get_or_create_settings(unit.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    lines_for_dev: List[dict] = []
    parsed_lines: Optional[List[dict]] = None
    if "lines" in patch:
        raw_lines = body.lines if body.lines is not None else []
        parsed_lines, err = _strict_lines_from_body(
            list(raw_lines), include_product_code=True
        )
        if err:
            raise HTTPException(status_code=422, detail=err)
        if parsed_lines:
            ensure_product_master_labels(unit.company_id, parsed_lines, db)
            db.flush()
            enrich_actual_lines_product_codes(unit.company_id, parsed_lines, db)
        lines_for_dev = list(parsed_lines) if parsed_lines else []
    else:
        an = _opt_str(body.actual_item_name)
        if an and body.actual_value is not None:
            try:
                lines_for_dev = [{"label": an.strip(), "value": float(body.actual_value)}]
            except (TypeError, ValueError):
                lines_for_dev = []
        else:
            lines_for_dev = []
        if lines_for_dev:
            ensure_product_master_labels(unit.company_id, lines_for_dev, db)
            db.flush()
            enrich_actual_lines_product_codes(unit.company_id, lines_for_dev, db)

    # 第7条逸脱: product_code 優先・両方コード無しのときのみ label。数量・順序は見ない。
    is_dev = is_actual_deviation_from_article7(unit.company_id, lines_for_dev, db)
    if is_dev:
        dr = getattr(body, "deviation_reason", None)
        reason_ok = str(dr).strip() if dr is not None else ""
        if not reason_ok:
            raise HTTPException(
                status_code=422,
                detail="7条に無い作業です。理由を入力してください",
            )
        deviation_reason_saved = reason_ok
    else:
        deviation_reason_saved = None

    if "lines" in patch:
        lines = parsed_lines if parsed_lines is not None else []
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

    if is_dev:
        unit.is_article7_deviation = True
        unit.is_deviation = True
        unit.deviation_reason = deviation_reason_saved
    else:
        unit.is_article7_deviation = False
        unit.is_deviation = False
        unit.deviation_reason = None

    unit.actual_at = datetime.utcnow()

    if "pattern_a" in patch:
        unit.pattern_a = patch["pattern_a"]
    if "pattern_b" in patch:
        unit.pattern_b = patch["pattern_b"]

    # 現場申告（B のみ）。system_pattern とは独立。B 未チェックでクリア
    if "pattern_b" in patch:
        unit.user_pattern = "B" if patch.get("pattern_b") else None
    elif "user_pattern" in patch:
        _up = patch.get("user_pattern")
        unit.user_pattern = "B" if (_up is not None and str(_up).strip().upper() == "B") else None

    if unit.planned_value is not None and unit.actual_value is not None:
        unit.diff_value = unit.actual_value - unit.planned_value

    _flush_then_recompute_past_missing(db, unit.company_id)
    _recompute_unit_derived(unit, settings, db)
    _audit_x_save(unit, settings, f"POST /work/{unit_id}/actual", "pre_commit")
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    _audit_x_save(unit, settings, f"POST /work/{unit_id}/actual", "post_commit")

    logger.warning(
        "[measureos.work.hook] POST /work/%s/actual committed company_id=%r actual_at=%r actual_value=%r lines_json_set=%s",
        unit_id,
        unit.company_id,
        unit.actual_at.isoformat() if unit.actual_at else None,
        unit.actual_value,
        bool(unit.actual_lines_json and str(unit.actual_lines_json).strip()),
    )

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
    raise_if_closed(unit)
    settings = _get_or_create_settings(unit.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    if "lines" in patch:
        _backfill_stored_planned_line_ids(unit)
        raw_lines = body.lines if body.lines is not None else []
        old_parsed = _parse_lines_json(unit.planned_lines_json)
        lines, err = _strict_lines_from_body(
            list(raw_lines),
            include_due_date=True,
            include_line_id=True,
            include_product_code=True,
        )
        if err:
            raise HTTPException(status_code=422, detail=err)
        _merge_due_from_previous(lines, old_parsed)
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

    _flush_then_recompute_past_missing(db, unit.company_id)
    _recompute_unit_derived(unit, settings, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(unit.company_id, unit.task_id, unit.process_id,
                                unit.user_id, unit.business_date, db)
    return _unit_to_out(unit, settings, db, prev_unit)


@router.post(
    "/work/{unit_id}/planned-due",
    summary="Merge due_date onto planned lines only (Article 7; match line_id)",
)
def merge_planned_due(
    unit_id: int,
    body: schemas.PlannedDueMergeIn,
    db: Session = Depends(get_db),
):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    raise_if_closed(unit)
    settings = _get_or_create_settings(unit.company_id, db)
    _backfill_stored_planned_line_ids(unit)
    base = _parse_lines_json(getattr(unit, "planned_lines_json", None))
    if not base:
        raise HTTPException(status_code=400, detail="予告行がありません")
    if not body.entries:
        prev_unit = _find_prev_unit(
            unit.company_id, unit.task_id, unit.process_id, unit.user_id, unit.business_date, db
        )
        return _unit_to_out(unit, settings, db, prev_unit)
    for entry in body.entries:
        lid = (entry.line_id or "").strip()
        if not lid:
            raise HTTPException(status_code=422, detail="line_id が空です")
        matched = None
        for row in base:
            if str(row.get("line_id") or "").strip() == lid:
                matched = row
                break
        if matched is None:
            raise HTTPException(
                status_code=422,
                detail=f"line_id に一致する予告行がありません: {lid!r}",
            )
        if "due_date" not in entry.model_fields_set:
            continue
        raw = entry.due_date
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            matched.pop("due_date", None)
        else:
            nd = _norm_due_date(str(raw).strip())
            if nd is None:
                raise HTTPException(
                    status_code=422,
                    detail="due_date は YYYY-MM-DD で指定してください",
                )
            matched["due_date"] = nd
    unit.planned_lines_json = _lines_json_dumps(base)
    _flush_then_recompute_past_missing(db, unit.company_id)
    _recompute_unit_derived(unit, settings, db)
    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    prev_unit = _find_prev_unit(
        unit.company_id, unit.task_id, unit.process_id, unit.user_id, unit.business_date, db
    )
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
    raise_if_closed(unit)
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
    current_biz = calc_business_date(reference_utc_now(), settings, db)
    if unit.business_date >= current_biz:
        unit.is_missing = False

    _flush_then_recompute_past_missing(db, unit.company_id)

    st = (unit.status or "normal").strip().lower()
    if st not in ("closed", "red"):
        _recompute_unit_derived(unit, settings, db)
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
def list_work(
    company_id: str,
    trace_unit_id: Optional[int] = Query(
        None,
        description="デバッグ: この id の unit をコミット後に DB 再読込し、一覧レスポンスと併せて追跡ログする",
    ),
    db: Session = Depends(get_db),
):
    settings = _get_or_create_settings(company_id, db)
    wet = settings.work_end_time or time(17, 0)

    # 表示は200件だが、updated_at が古い行はページ外になりがち。時刻依存の青は全行へ反映する。
    all_company_units = (
        db.query(models.WorkUnit)
        .filter_by(company_id=company_id)
        .all()
    )
    recompute_count = 0
    for u in all_company_units:
        st0 = (u.status or "").strip().lower()
        if st0 in ("closed", "red"):
            continue
        before_status = u.status
        _recompute_unit_derived(u, settings, db)
        after_status = u.status
        hp = _has_planned_nonzero(u, settings)
        hs = u.started_at is not None
        ha = _has_actual_signal(u, settings)
        ha_meaningful = _has_meaningful_actual(u, settings)
        incomplete_b = incomplete_implies_status_blue(
            has_planned_nonzero=hp,
            has_meaningful_actual=ha_meaningful,
            business_date=u.business_date,
            company_id=u.company_id,
            settings=settings,
            db=db,
        )
        now_j = reference_now_jst()
        boundary_j = next_work_end_boundary_jst(u.business_date, wet, u.company_id, db)
        inst = inspect(u)
        unit_modified = bool(getattr(inst, "modified", False))
        log_suffix = " TRACE_TARGET" if trace_unit_id is not None and u.id == trace_unit_id else ""
        logger.info(
            "[measureos.work.list_recompute] company_id=%r unit_id=%s business_date=%s "
            "before_status=%r after_status=%r hp=%s hs=%s ha=%s ha_meaningful=%s "
            "now_jst=%s next_work_end_boundary_jst=%s incomplete_blue=%s unit_modified=%s%s",
            company_id,
            u.id,
            u.business_date,
            before_status,
            after_status,
            hp,
            hs,
            ha,
            ha_meaningful,
            now_j.isoformat(),
            boundary_j.isoformat(),
            incomplete_b,
            unit_modified,
            log_suffix,
        )
        recompute_count += 1

    promote_blue_to_red_after_judgement(company_id, db)

    dirty_n = len(db.dirty)
    commit_called = False
    if dirty_n > 0:
        db.commit()
        commit_called = True
    logger.info(
        "[measureos.work.list_recompute_done] company_id=%r all_units=%s recomputed_non_terminal=%s "
        "session_dirty_before_commit=%s commit_called=%s",
        company_id,
        len(all_company_units),
        recompute_count,
        dirty_n,
        commit_called,
    )
    if recompute_count > 0 and dirty_n == 0:
        logger.warning(
            "[measureos.work.list_recompute_done] company_id=%r recomputed=%s but session_dirty=0 "
            "(期待: 属性更新があれば dirty になる)",
            company_id,
            recompute_count,
        )

    sort_key = func.coalesce(models.WorkUnit.updated_at, models.WorkUnit.created_at)
    units = (
        db.query(models.WorkUnit)
        .filter_by(company_id=company_id)
        .order_by(sort_key.desc().nulls_last(), models.WorkUnit.id.desc())
        .limit(200)
        .all()
    )
    out = [_unit_to_out(u, settings, db) for u in units]
    if trace_unit_id is not None:
        tr = (
            db.query(models.WorkUnit)
            .filter(
                models.WorkUnit.id == trace_unit_id,
                models.WorkUnit.company_id == company_id,
            )
            .first()
        )
        resp_row = next((r for r in out if r.get("id") == trace_unit_id), None)
        logger.warning(
            "[measureos.work.list_trace] trace_unit_id=%s company_id=%r "
            "db_status=%r db_planned_value=%r db_started_at=%r db_actual_value=%r db_actual_at=%r "
            "response_status=%r response_in_payload=%s commit_called=%s",
            trace_unit_id,
            company_id,
            getattr(tr, "status", None) if tr else None,
            getattr(tr, "planned_value", None) if tr else None,
            getattr(tr, "started_at", None) if tr else None,
            getattr(tr, "actual_value", None) if tr else None,
            getattr(tr, "actual_at", None) if tr else None,
            (resp_row or {}).get("status") if resp_row is not None else None,
            resp_row is not None,
            commit_called,
        )
    return out
