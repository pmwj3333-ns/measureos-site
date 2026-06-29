import copy
import hashlib
import json
import logging
import math
import uuid
from datetime import datetime, date as date_type, time
from typing import Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
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
from app.services.test_clock import reference_utc_now
from app.services.work_unit_guard import is_closed, raise_if_closed
from app.services.status_history import (
    append_work_unit_status_history_if_changed,
    norm_work_unit_status,
)
from app.services.judgement_promote import (
    carryover_implies_status_blue_unit,
    compute_red_deadline_jst,
    incomplete_implies_status_blue,
    next_work_end_boundary_jst,
    promote_blue_to_red_after_judgement,
    reference_now_jst,
)
from app.services.package_rules import is_phase2_enabled
from app.services.company_validator import validate_company_id, validate_unit_company_id
from app.services.office_session_scope import (
    require_session_company_match,
    require_session_company_row,
)
from app.services.article7_deviation import is_actual_deviation_from_article7
from app.services.product_master import (
    enrich_actual_lines_product_codes,
    ensure_product_master_labels,
)
from app.services.work_unit_clone import (
    clone_work_unit_row,
    strip_derived_columns_for_fact_snapshot,
    sync_planned_at_with_planned_facts,
)
from app.services.anomaly_classification import (
    build_storage_from_request,
    parse_classification_json,
)
from app.services.actual_revision import (
    compute_actual_revision_meta_for_unit,
    enrich_units_actual_revision_meta,
)

router = APIRouter(tags=["作業記録"])
logger = logging.getLogger(__name__)


def _guard_company_session(request: Request, company_id: str) -> str:
    return require_session_company_match(request, company_id)


def _guard_unit_session(request: Request, unit: models.WorkUnit) -> None:
    require_session_company_row(request, unit.company_id)


def _touch_updated(unit: models.WorkUnit) -> None:
    """一覧の並び（updated_at desc）用。保存直前に呼ぶ。"""
    unit.updated_at = datetime.utcnow()


# ─── ヘルパー ────────────────────────────────────────────────

def _opt_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def _opt_memo(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:4000]


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


def _normalize_used_material_dict(it: dict) -> Optional[dict]:
    d: dict = {}
    lab = str(it.get("label", "") or "").strip()
    if lab:
        d["label"] = lab
    v = it.get("value")
    if v is not None:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            fv = None
        if fv is not None and math.isfinite(fv):
            d["value"] = fv
    u = it.get("unit")
    if u is not None and str(u).strip():
        d["unit"] = str(u).strip()
    ln = it.get("lot_no")
    if ln is not None and str(ln).strip():
        d["lot_no"] = str(ln).strip()
    return d if d else None


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
        if not lb:
            continue
        v = it.get("value")
        fv: Optional[float] = None
        if v is not None and str(v).strip() != "":
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(fv):
                continue
        row: dict = {"label": lb}
        if fv is not None:
            row["value"] = fv
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
        ums_raw = it.get("used_materials")
        if isinstance(ums_raw, list) and ums_raw:
            ums_clean: List[dict] = []
            for uu in ums_raw:
                if isinstance(uu, dict):
                    nd_um = _normalize_used_material_dict(uu)
                    if nd_um:
                        ums_clean.append(nd_um)
            if ums_clean:
                row["used_materials"] = ums_clean
        lm = it.get("line_memo")
        if lm is not None and str(lm).strip():
            row["line_memo"] = str(lm).strip()
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


_MAX_USED_MATERIALS_ROWS = 200
_PER_LINE_USED_MATERIALS_MAX = 100


def _used_material_rows_to_dicts(
    rows: List[schemas.UsedMaterialIn],
) -> Tuple[List[dict], Optional[str]]:
    """使用物: 空行はスキップ。件数上限は呼び出し側で適用する。"""
    out: List[dict] = []
    for row in rows:
        lb = (row.label or "").strip()
        unit_s = (row.unit or "").strip() if row.unit is not None else ""
        lot_s = (row.lot_no or "").strip() if row.lot_no is not None else ""
        val_raw = row.value
        fv: Optional[float] = None
        if val_raw is not None:
            try:
                fv = float(val_raw)
            except (TypeError, ValueError):
                return [], "使用物の数量の形式が不正な行があります"
            if not math.isfinite(fv):
                return [], "使用物の数量の形式が不正な行があります"
        if not lb and not unit_s and not lot_s and fv is None:
            continue
        dct: dict = {}
        if lb:
            dct["label"] = lb
        if fv is not None:
            dct["value"] = fv
        if unit_s:
            dct["unit"] = unit_s
        if lot_s:
            dct["lot_no"] = lot_s
        if not dct:
            continue
        out.append(dct)
    return out, None


def _used_materials_from_body(
    rows: List[schemas.UsedMaterialIn],
) -> Tuple[List[dict], Optional[str]]:
    """使用物ログ（トップレベル廃止予定の互換用）。空行はスキップ。"""
    if len(rows) > _MAX_USED_MATERIALS_ROWS:
        return [], f"使用物は最大{_MAX_USED_MATERIALS_ROWS}行までです"
    return _used_material_rows_to_dicts(rows)


def _legacy_used_materials_list_from_column(unit: models.WorkUnit) -> List[dict]:
    raw = getattr(unit, "used_materials_json", None)
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list) or not data:
        return []
    out: List[dict] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        nd = _normalize_used_material_dict(it)
        if nd:
            out.append(nd)
    return out


def _flatten_used_materials_from_actual_line_dicts(lines: List[dict]) -> List[dict]:
    flat: List[dict] = []
    for ln in lines:
        if not isinstance(ln, dict):
            continue
        ums = ln.get("used_materials")
        if not isinstance(ums, list):
            continue
        for it in ums:
            if not isinstance(it, dict):
                continue
            nd = _normalize_used_material_dict(it)
            if nd:
                flat.append(nd)
    return flat


def used_materials_for_api(unit: models.WorkUnit) -> Optional[List[dict]]:
    """GET 応答用: actual_lines 内 used_materials を優先して平坦化、無ければ used_materials_json。"""
    parsed = _parse_lines_json(getattr(unit, "actual_lines_json", None))
    if parsed:
        flat = _flatten_used_materials_from_actual_line_dicts(parsed)
        if flat:
            return flat
    leg = _legacy_used_materials_list_from_column(unit)
    return leg or None


def _join_line_labels(lines: List[dict], sep: str = " · ") -> Optional[str]:
    if not lines:
        return None
    return sep.join(str(x["label"]) for x in lines)


def _sum_line_values_optional(lines: List[dict]) -> Optional[float]:
    """各行の value を足す。1つも有限値がなければ None（0 補完はしない）。"""
    total = 0.0
    any_v = False
    for x in lines:
        if not isinstance(x, dict) or "value" not in x:
            continue
        raw = x.get("value")
        if raw is None:
            continue
        try:
            fv = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(fv):
            continue
        total += fv
        any_v = True
    return total if any_v else None


def _strict_lines_from_body(
    rows: List[schemas.WorkLineIn],
    *,
    include_due_date: bool = False,
    include_line_id: bool = False,
    include_product_code: bool = False,
    include_used_materials: bool = False,
    include_line_memo: bool = False,
    allow_missing_main_qty: bool = False,
) -> Tuple[List[dict], Optional[str]]:
    """lines 指定時。空行は無視。数量だけの行はエラー。
    allow_missing_main_qty が True のとき（予告 POST のみ）商品名のみの行を許可（value は付与しない）。"""
    complete: List[dict] = []
    total_um = 0
    for row in rows:
        lb = (row.label or "").strip()
        v = row.value
        if not lb and v is None:
            continue
        if not lb and v is not None:
            return None, "数量だけ入力された行があります。名前と数量をセットで入力してください"
        dct: dict = {"label": lb}
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None, "数量の形式が不正な行があります"
            if not math.isfinite(fv):
                return None, "数量の形式が不正な行があります"
            dct["value"] = fv
        elif not allow_missing_main_qty:
            return None, "名前だけ入力された行があります。数量も入力してください"
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
        if include_used_materials:
            if "used_materials" in row.model_fields_set:
                ums = row.used_materials if row.used_materials is not None else []
                if len(ums) > _PER_LINE_USED_MATERIALS_MAX:
                    return (
                        None,
                        f"1行あたりの使用物は最大{_PER_LINE_USED_MATERIALS_MAX}行までです",
                    )
                udicts, uerr = _used_material_rows_to_dicts(list(ums))
                if uerr:
                    return None, uerr
                total_um += len(udicts)
                if total_um > _MAX_USED_MATERIALS_ROWS:
                    return (
                        None,
                        f"使用物は全体で最大{_MAX_USED_MATERIALS_ROWS}行までです",
                    )
                dct["used_materials"] = udicts
        if include_line_memo:
            if "line_memo" in row.model_fields_set:
                raw_memo = row.line_memo
                if raw_memo is not None and str(raw_memo).strip():
                    dct["line_memo"] = str(raw_memo).strip()
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
    reg = getattr(unit, "planned_registered_at", None) is not None
    if not reg:
        return []
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
    legacy_um = _legacy_used_materials_list_from_column(unit)

    lines: List[dict] = []
    if parsed:
        lines = copy.deepcopy(parsed)
    else:
        v = unit.actual_value
        if v is None or not math.isfinite(float(v)):
            return []
        fv = float(v)
        if im == "logistics":
            lab = _opt_str(unit.actual_work_label) or _opt_str(unit.actual_work_type)
            if not lab:
                return []
            lines = [{"label": lab, "value": fv}]
        else:
            n = (unit.actual_item_name or "").strip()
            if not n:
                return []
            lines = [{"label": n, "value": fv}]

    if legacy_um and lines:
        any_um = False
        for ln in lines:
            if not isinstance(ln, dict):
                continue
            ums = ln.get("used_materials")
            if isinstance(ums, list) and len(ums) > 0:
                any_um = True
                break
        if not any_um:
            first = dict(lines[0])
            first["used_materials"] = copy.deepcopy(legacy_um)
            lines[0] = first
    return lines


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
    - planned_lines_json にラベル付きの行がある（数量未入力の予告も含む）
    - planned_lines_json に数量≠0 の行がある
    - planned_value が実数かつ≠0（NULL は false）
    - 子テーブル planned 行に quantity≠0 がある（v2）

    planned_registered_at 無し / 空配列 / ラベルも数量も無い行のみ → false。
    """
    if getattr(unit, "planned_registered_at", None) is None:
        return False
    parsed = _parse_lines_json(getattr(unit, "planned_lines_json", None))
    if parsed:
        json_hit = False
        json_named = False
        for it in parsed:
            if not isinstance(it, dict):
                continue
            lb = str(it.get("label", "")).strip()
            if not lb:
                continue
            json_named = True
            raw = it.get("value")
            if raw is not None and raw != "" and _numeric_nonzero(raw):
                json_hit = True
                break
        if json_hit or json_named:
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


def _is_empty_actual_report(unit: models.WorkUnit, settings: models.CompanySettings) -> bool:
    """actual_at あり・実績内容なし（順序は成立、結果不備）。"""
    return unit.actual_at is not None and not _has_meaningful_actual(unit, settings)


def _phase1_completely_empty_legacy_triplet(unit: models.WorkUnit) -> bool:
    """
    フェーズ1: planned_value / started_at / actual_value がすべて未入力。
    この状態では blue/red にしない（actual_at のみなどは対象外）。
    未登録の予告ドラフト（DB に値が残っていても planned_registered_at が無い）は planned 未入力扱い。
    """
    pv = getattr(unit, "planned_value", None)
    if getattr(unit, "planned_registered_at", None) is None:
        pv = None
    return (
        pv is None
        and getattr(unit, "started_at", None) is None
        and getattr(unit, "actual_value", None) is None
    )


def _has_actual_signal(unit: models.WorkUnit, settings: models.CompanySettings) -> bool:
    """実績あり: 数量・明細ベースのみ（actual_at だけでは True にしない）。フェーズ1"""
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
    record_history: bool = True,
) -> None:
    """
    第5条フェーズ1: system_pattern を決める（終端ステータス以外）。
    ここでは status を blue にせず normal にリセットし、
    _sync_status_blue_from_derived_flags が is_invalid_flow / is_diff_anomaly /
    is_article7_deviation のみで blue を確定する。

    A*/B*/7条逸脱 の判定式は従来どおり。
    未登録班長でも pattern は空・status は後段まで normal。

    force_status が closed/red のときは終了のみ（pattern は変更しない）。
    status が実際に変わったときだけ work_unit_status_history に追記（db があるとき）。
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
        empty_actual_report = _is_empty_actual_report(unit, settings)

        unreg = bool(getattr(unit, "is_unregistered_user", False))
        if unreg:
            unit.system_pattern = ""
            unit.status = "normal"
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
                "[measureos.judge] unit_id=%s company_id=%r unreg=True -> pattern='' status=normal (phase1)",
                getattr(unit, "id", None),
                getattr(unit, "company_id", None),
            )
            return

        sys_a = ((not hp) and (hs or ha)) or ((not hs) and ha)
        if empty_actual_report:
            if hs:
                sys_a = False
            else:
                sys_a = True
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
        b_empty_actual = empty_actual_report and hs
        sys_b = b_no_planned_actual or b_tolerance or b_empty_actual

        parts: List[str] = []
        if sys_a:
            parts.append("A*")
        # B*: 許容超過 / 実績内容なし。予告なし実績は A* のみ。
        if b_tolerance or b_empty_actual:
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
        # フェーズ1: incomplete・順序系でここでは blue にしない（後段 sync がフラグのみで blue）
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
        if db is not None and record_history:
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
    フェーズ1: is_missing は参照用のみ（status は変更しない）。
    - status が closed のときは常に is_missing=False（事務確定後は欠損概念なし）。
    - それ以外: business_date が現行・未来（>= current_business_date）なら False。
    - 過去営業日のみ、参照時刻がその日の judgement_time を厳密に過ぎたあとだけ欠損トリプレットを評価。
    """

    cur = (unit.status or "").strip().lower()
    if cur == "closed":
        unit.is_missing = False
        return

    def _missing_triplet() -> bool:
        return (
            unit.planned_value is None
            or unit.actual_value is None
            or unit.started_at is None
        )

    ref = reference_utc_now()
    current_biz = calc_business_date(ref, settings, db)

    if unit.business_date >= current_biz:
        unit.is_missing = False
        return

    ref_jst = reference_now_jst()
    jt = settings.judgement_time or time(13, 0)
    boundary_dt = datetime.combine(ref_jst.date(), jt, tzinfo=ref_jst.tzinfo)
    if ref_jst <= boundary_dt:
        unit.is_missing = False
        return

    unit.is_missing = _missing_triplet()


def _update_flags(unit: models.WorkUnit, settings: models.CompanySettings) -> None:
    """
    補助フラグ。
    - is_diff_anomaly: 結果不備（数量差・実績内容なし）。
      system_pattern の B* は「予告なし+実績」も含むが、is_diff_anomaly とは別分類。
    - is_invalid_flow: A*（プロセス不備）または 実績あり・着手なし
    """
    segs = [x.strip() for x in (unit.system_pattern or "").split(",") if x.strip()]
    hp = _has_planned_nonzero(unit, settings)
    ha = _has_actual_signal(unit, settings)
    empty_actual_report = _is_empty_actual_report(unit, settings)
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
    unit.is_diff_anomaly = b_tolerance or (
        empty_actual_report and unit.started_at is not None
    )
    # 順序不備: A*（プロセス不備）に該当、または 実績あり・着手なし
    unit.is_invalid_flow = bool(
        "A*" in segs
        or (_has_actual_signal(unit, settings) and unit.started_at is None)
        or (empty_actual_report and unit.started_at is None)
    )


def _sync_status_blue_from_derived_flags(
    unit: models.WorkUnit,
    db: Session,
    *,
    record_history: bool = True,
) -> None:
    """
    フェーズ1（シャドウ応答）: status=blue は次。
      - is_invalid_flow / is_diff_anomaly / is_article7_deviation（即時）
      - actual_at なし かつ effective_date > business_date（持ち越し）
    is_missing / 未登録 / is_deviation 単体では blue にしない。
    closed/red は変更しない。
    """
    _ = record_history
    st = (unit.status or "").strip().lower()
    if st in ("closed", "red"):
        return
    if (
        bool(getattr(unit, "is_invalid_flow", False))
        or bool(getattr(unit, "is_diff_anomaly", False))
        or bool(getattr(unit, "is_article7_deviation", False))
    ):
        unit.status = "blue"
        return
    settings = _get_or_create_settings(unit.company_id, db)
    if carryover_implies_status_blue_unit(unit, settings):
        unit.status = "blue"
        return
    unit.status = "normal"


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


def _compute_derived_shadow(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
) -> models.WorkUnit:
    """
    DB を更新せずレスポンス用に派生値を計算したメモリ上の WorkUnit。
    DB に保存された closed / red は終端事実として維持し、それ以外は現時点での評価で判定する。

    フェーズ1: status=blue は _sync_status_blue_from_derived_flags でのみ確定し、
    is_missing だけでは昇格しない。
    """
    shadow = clone_work_unit_row(unit)
    st0 = norm_work_unit_status(unit.status)
    rh = False

    _apply_user_classification(shadow, settings)

    if st0 == "closed":
        _apply_minimal_judgement(
            shadow, settings, db=db, force_status="closed", record_history=rh
        )
        _update_is_missing_summary(shadow, settings, db)
        _update_flags(shadow, settings)
        return shadow

    if st0 == "red":
        _apply_minimal_judgement(
            shadow, settings, db=db, force_status="red", record_history=rh
        )
        _update_is_missing_summary(shadow, settings, db)
        _update_flags(shadow, settings)
        return shadow

    shadow.status = "normal"
    _apply_minimal_judgement(shadow, settings, db=db, record_history=rh)
    _update_is_missing_summary(shadow, settings, db)
    _update_flags(shadow, settings)
    _sync_status_blue_from_derived_flags(shadow, db, record_history=rh)
    return shadow


def _normalized_response_status(shadow: models.WorkUnit) -> str:
    s = (shadow.status or "").strip().lower()
    if s in ("closed", "red", "blue"):
        return s
    return "normal"


def _unit_to_out(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
    prev_unit: Optional[models.WorkUnit] = None,
    *,
    office_chain_hint: Optional[str] = None,
) -> dict:
    shadow = _compute_derived_shadow(unit, settings, db)
    im = _norm_input_mode(settings)
    plines = _planned_lines_for_response(unit, im)
    alines = _actual_lines_for_response(unit, im)
    prev_plines = _planned_lines_for_response(prev_unit, im) if prev_unit else []
    st_out = _normalized_response_status(shadow)
    jt = settings.judgement_time or time(13, 0)
    judgement_red_deadline_at = None
    if st_out == "blue" and is_phase2_enabled(settings):
        judgement_red_deadline_at = compute_red_deadline_jst(
            unit.business_date, jt, unit.company_id, db
        ).isoformat()

    deviation_reason_out = str(getattr(unit, "deviation_reason", None) or "").strip()
    deviation_reason_out = deviation_reason_out or None

    reg = getattr(unit, "planned_registered_at", None) is not None
    show_planned_derived = reg or bool(plines)

    return {
        "id":                 unit.id,
        "company_id":         unit.company_id,
        "task_id":            unit.task_id,
        "process_id":         unit.process_id,
        "user_id":            unit.user_id,
        "business_date":      str(unit.business_date),
        "planned_at":         unit.planned_at.isoformat() if reg and getattr(unit, "planned_at", None) else None,
        "planned_registered_at": unit.planned_registered_at.isoformat()
        if getattr(unit, "planned_registered_at", None)
        else None,
        "created_at":         unit.created_at.isoformat() if getattr(unit, "created_at", None) else None,
        "input_source":       getattr(unit, "input_source", None) or None,
        "business_date_source": getattr(unit, "business_date_source", None),
        "business_date_debug": _parse_unit_business_date_debug(unit),
        "input_mode":         im,
        "planned_work_type":  unit.planned_work_type if show_planned_derived else None,
        "planned_work_label": unit.planned_work_label if show_planned_derived else None,
        "planned_item_name":  unit.planned_item_name if show_planned_derived else None,
        "planned_lines":      plines,
        "planned_value":      unit.planned_value if show_planned_derived else None,
        "started_at":         unit.started_at.isoformat() if unit.started_at else None,
        "actual_work_type":   unit.actual_work_type,
        "actual_work_label":  unit.actual_work_label,
        "actual_item_name":   unit.actual_item_name,
        "actual_lines":       alines,
        "actual_value":       unit.actual_value,
        "actual_at":          unit.actual_at.isoformat() if unit.actual_at else None,
        "actual_memo":        _opt_str(getattr(unit, "actual_memo", None)),
        "used_materials":     used_materials_for_api(unit),
        "used_materials_json": getattr(unit, "used_materials_json", None),
        "pattern_a":          unit.pattern_a,
        "pattern_b":          unit.pattern_b,
        "user_pattern":       getattr(unit, "user_pattern", None) or None,
        "anomaly_classification": parse_classification_json(
            getattr(unit, "anomaly_classification_json", None)
        ),
        "system_pattern":     getattr(shadow, "system_pattern", None) or "",
        "status":             st_out,
        "judgement_red_deadline_at": judgement_red_deadline_at,
        "diff_value":         unit.diff_value,
        "is_missing":         bool(shadow.is_missing),
        "is_invalid_flow":    bool(getattr(shadow, "is_invalid_flow", False)),
        "is_diff_anomaly":    bool(getattr(shadow, "is_diff_anomaly", False)),
        "anomaly_started_at": unit.anomaly_started_at.isoformat()
        if getattr(unit, "anomaly_started_at", None)
        else None,
        "is_unregistered_user": bool(shadow.is_unregistered_user),
        "user_source":        shadow.user_source or "master",
        "is_deviation":       bool(getattr(unit, "is_deviation", False)),
        "is_article7_deviation": bool(getattr(unit, "is_article7_deviation", False)),
        "deviation_reason":   deviation_reason_out,
        "prev_planned_value": prev_unit.planned_value if prev_unit else None,
        "prev_planned_work_type": prev_unit.planned_work_type if prev_unit else None,
        "prev_planned_work_label": prev_unit.planned_work_label if prev_unit else None,
        "prev_planned_item_name": prev_unit.planned_item_name if prev_unit else None,
        "prev_planned_lines": prev_plines,
        "unit":               settings.unit or "個",
        "office_chain_hint": (office_chain_hint if office_chain_hint is not None else ""),
        "reflection_status": _reflection_status_out(unit),
        "reflection_reject_reason_code": getattr(
            unit, "reflection_reject_reason_code", None
        ),
        "reflection_reject_reason_detail": getattr(
            unit, "reflection_reject_reason_detail", None
        ),
        "is_actual_revision": False,
        "actual_revision_detail_line": None,
        "actual_revision_notice_strong": False,
    }


def _reflection_status_out(unit: models.WorkUnit) -> str:
    raw = getattr(unit, "reflection_status", None)
    s = str(raw or "").strip().lower()
    if s in ("pending", "accepted", "rejected"):
        return s
    return "pending"


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


def _resumable_open_tip_for_calendar_day(
    db: Session,
    company_id: str,
    task_id: str,
    process_id: str,
    user_id: str,
    biz_date: date_type,
) -> Optional[models.WorkUnit]:
    """
    同日・同一キーで「いまの先頭行」（id 最大の 1 件）だけを見る。

    append-only のため、同日に複数行があり古い行が未報告のまま残っていても、
    それより新しい行で実績済みなら新規壳を作る（古い行に戻さない）。
    """
    tip = (
        db.query(models.WorkUnit)
        .filter(
            models.WorkUnit.company_id == company_id,
            models.WorkUnit.task_id == task_id,
            models.WorkUnit.process_id == process_id,
            models.WorkUnit.user_id == user_id,
            models.WorkUnit.business_date == biz_date,
        )
        .order_by(models.WorkUnit.id.desc())
        .first()
    )
    if tip is None:
        return None
    if is_closed(tip):
        return None
    if tip.actual_at is not None:
        return None
    return tip


def _unit_to_out_with_hint(
    unit: models.WorkUnit,
    settings: models.CompanySettings,
    db: Session,
    prev_unit: Optional[models.WorkUnit] = None,
) -> dict:
    return _unit_to_out(unit, settings, db, prev_unit, office_chain_hint="")


# ─── エンドポイント ──────────────────────────────────────────

@router.get("/work/next-business-date", summary="次の営業日を返す（行は作らない）")
def get_next_business_date_only(
    request: Request,
    company_id: str,
    current_business_date: str,
    db: Session = Depends(get_db),
):
    cid = _guard_company_session(request, company_id)
    _get_or_create_settings(cid, db)
    cur = date_type.fromisoformat(current_business_date)
    nxt = next_business_day(cur, cid, db)
    return {"business_date": str(nxt)}


@router.post(
    "/work",
    summary="今日の作業記録の壳（未報告なら既存行を返し、実績済みなら新規 INSERT・append-only）",
)
def create_work_shell(
    body: schemas.WorkUnitQuery, request: Request, db: Session = Depends(get_db)
):
    cid = _guard_company_session(request, body.company_id)
    validate_company_id(db, cid)
    body = body.model_copy(update={"company_id": cid})
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

    tip = _resumable_open_tip_for_calendar_day(
        db,
        body.company_id,
        body.task_id,
        body.process_id,
        body.user_id,
        biz_date,
    )
    if tip is not None:
        prev_unit = _find_prev_unit(
            body.company_id,
            body.task_id,
            body.process_id,
            body.user_id,
            biz_date,
            db,
        )
        logger.warning(
            "[measureos.work.hook] POST /work resumed unit_id=%s company_id=%r business_date=%s "
            "has_started_at=%s has_actual_at=%s",
            tip.id,
            tip.company_id,
            tip.business_date,
            tip.started_at is not None,
            tip.actual_at is not None,
        )
        return _unit_to_out_with_hint(tip, settings, db, prev_unit)

    # 実績報告済みなど、未報告の行が無いときだけ新規壳を追加する（append-only）。
    unit = models.WorkUnit(
        company_id=body.company_id,
        task_id=body.task_id,
        process_id=body.process_id,
        user_id=body.user_id,
        business_date=biz_date,
    )
    unit.business_date_source = biz_source
    unit.business_date_debug_json = json.dumps(biz_debug, ensure_ascii=False)
    unit.created_at = datetime.utcnow()
    db.add(unit)
    db.flush()

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
    return _unit_to_out_with_hint(unit, settings, db, prev_unit)


@router.post("/work/next-day", summary="次の営業日を開始する（着手含む）")
def start_next_day(
    body: schemas.NextDayQuery, request: Request, db: Session = Depends(get_db)
):
    cid = _guard_company_session(request, body.company_id)
    validate_company_id(db, cid)
    body = body.model_copy(update={"company_id": cid})
    settings     = _get_or_create_settings(body.company_id, db)
    current_date = date_type.fromisoformat(body.current_business_date)
    next_date, next_dbg = next_business_day_detailed(current_date, body.company_id, db)
    next_dbg["api"] = "POST /work/next-day"

    unit = (
        db.query(models.WorkUnit)
        .filter_by(
            company_id=body.company_id,
            task_id=body.task_id,
            process_id=body.process_id,
            user_id=body.user_id,
            business_date=next_date,
        )
        .order_by(models.WorkUnit.id.desc())
        .first()
    )

    if unit is not None and is_closed(unit):
        unit = None

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

    _touch_updated(unit)
    db.commit()
    db.refresh(unit)

    prev_unit = _find_prev_unit(body.company_id, body.task_id, body.process_id,
                                body.user_id, next_date, db)
    return _unit_to_out_with_hint(unit, settings, db, prev_unit)


@router.get(
    "/work/{unit_id}/status-history",
    response_model=List[schemas.WorkUnitStatusHistoryItem],
    summary="status 変化履歴（新しい順・読み取り専用）",
)
def get_work_unit_status_history(
    unit_id: int, request: Request, db: Session = Depends(get_db)
):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, unit)
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


def _copy_reflection_snapshot_from_peer(peer: models.WorkUnit, nu: models.WorkUnit) -> None:
    """strip_derived が reflection を pending に戻すため、完了 INSERT はピアの事務判断を引き継ぐ。"""
    nu.reflection_status = _reflection_status_out(peer)
    nu.reflection_reject_reason_code = getattr(peer, "reflection_reject_reason_code", None)
    nu.reflection_reject_reason_detail = getattr(peer, "reflection_reject_reason_detail", None)


@router.post(
    "/work/{unit_id}/close",
    summary="【事務】指定 ID の作業1件を承認・完了（closed スナップショット INSERT）",
)
def approve_close_work(unit_id: int, request: Request, db: Session = Depends(get_db)):
    src = db.get(models.WorkUnit, unit_id)
    if not src:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, src)
    validate_unit_company_id(db, src)
    settings = _get_or_create_settings(src.company_id, db)
    if is_closed(src):
        prev_unit = _find_prev_unit(
            src.company_id,
            src.task_id,
            src.process_id,
            src.user_id,
            src.business_date,
            db,
        )
        return _unit_to_out_with_hint(src, settings, db, prev_unit)

    shadow = _compute_derived_shadow(src, settings, db)
    if _normalized_response_status(shadow) not in ("blue", "red"):
        raise HTTPException(
            status_code=422,
            detail="完了対象の青・赤レコードがありません",
        )

    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _copy_reflection_snapshot_from_peer(src, nu)
    _apply_user_classification(nu, settings)
    db.add(nu)
    db.flush()
    _apply_minimal_judgement(nu, settings, db=db, force_status="closed")
    sync_planned_at_with_planned_facts(nu)
    _touch_updated(nu)

    now = datetime.utcnow()
    Sup = models.OfficeClosedWorkUnitSuppress
    if db.get(Sup, src.id) is None:
        db.add(Sup(peer_unit_id=src.id, created_at=now))

    db.commit()

    db.refresh(nu)
    prev_unit = _find_prev_unit(
        nu.company_id,
        nu.task_id,
        nu.process_id,
        nu.user_id,
        nu.business_date,
        db,
    )
    return _unit_to_out_with_hint(nu, settings, db, prev_unit)


@router.post("/work/{unit_id}/start", summary="着手を記録する")
def mark_started(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: schemas.StartedIn = Body(default_factory=schemas.StartedIn),
):
    src = db.get(models.WorkUnit, unit_id)
    if not src:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, src)
    validate_unit_company_id(db, src)
    raise_if_closed(src)
    if getattr(src, "planned_registered_at", None) is None:
        raise HTTPException(status_code=422, detail="先に予告登録を行ってください")
    settings = _get_or_create_settings(src.company_id, db)
    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _apply_user_classification(nu, settings)
    db.add(nu)
    db.flush()
    if nu.started_at is None:
        nu.started_at = datetime.utcnow()
    if (
        getattr(src, "planned_registered_at", None) is None
        and body.lines is not None
    ):
        lines, err = _strict_lines_from_body(
            list(body.lines),
            include_line_id=True,
            include_product_code=True,
            include_used_materials=True,
            allow_missing_main_qty=True,
        )
        if err:
            raise HTTPException(status_code=422, detail=err)
        if lines:
            for ln in lines:
                if isinstance(ln, dict):
                    ln.pop("line_memo", None)
                    ums = ln.get("used_materials")
                    if isinstance(ums, list) and len(ums) == 0:
                        ln.pop("used_materials", None)
            nu.planned_lines_json = _lines_json_dumps(lines)
            nu.planned_value = _sum_line_values_optional(lines)
            im = _norm_input_mode(settings)
            if im == "logistics":
                nu.planned_work_label = _join_line_labels(lines)
                nu.planned_work_type = None
                nu.planned_item_name = None
            else:
                nu.planned_item_name = _join_line_labels(lines)
                nu.planned_work_label = None
                nu.planned_work_type = None
    sync_planned_at_with_planned_facts(nu)
    _touch_updated(nu)
    db.commit()
    db.refresh(nu)
    prev_unit = _find_prev_unit(src.company_id, src.task_id, src.process_id,
                                src.user_id, src.business_date, db)
    return _unit_to_out_with_hint(nu, settings, db, prev_unit)


@router.post("/work/{unit_id}/actual", summary="実績を記録する")
def save_actual(
    unit_id: int,
    body: schemas.ActualIn,
    request: Request,
    db: Session = Depends(get_db),
):
    patch_preview = body.model_dump(exclude_unset=True)
    logger.warning(
        "[measureos.work.hook] POST /work/%s/actual body_keys=%s lines_in_body=%s",
        unit_id,
        sorted(patch_preview.keys()),
        "lines" in patch_preview,
    )
    src = db.get(models.WorkUnit, unit_id)
    if not src:
        logger.warning(
            "[measureos.work.hook] POST /work/%s/actual — no row (404)",
            unit_id,
        )
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, src)
    validate_unit_company_id(db, src)
    raise_if_closed(src)
    settings = _get_or_create_settings(src.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    um_parsed: Optional[List[dict]] = None
    if "used_materials" in patch:
        raw_um = body.used_materials if body.used_materials is not None else []
        um_parsed, um_err = _used_materials_from_body(list(raw_um))
        if um_err:
            raise HTTPException(status_code=422, detail=um_err)

    lines_for_dev: List[dict] = []
    parsed_lines: Optional[List[dict]] = None
    touch_line_um = False
    if "lines" in patch:
        raw_lines = body.lines if body.lines is not None else []
        for row in raw_lines:
            if "used_materials" in row.model_fields_set:
                touch_line_um = True
                break
        parsed_lines, err = _strict_lines_from_body(
            list(raw_lines),
            include_product_code=True,
            include_used_materials=True,
            include_line_memo=True,
        )
        if err:
            raise HTTPException(status_code=422, detail=err)
        if parsed_lines and "used_materials" in patch:
            if um_parsed:
                first = dict(parsed_lines[0])
                cur = (
                    list(first.get("used_materials") or [])
                    if isinstance(first.get("used_materials"), list)
                    else []
                )
                first["used_materials"] = cur + list(um_parsed)
                if not first["used_materials"]:
                    first.pop("used_materials", None)
                parsed_lines[0] = first
            else:
                first = dict(parsed_lines[0])
                first.pop("used_materials", None)
                parsed_lines[0] = first
        if parsed_lines:
            for ln in parsed_lines:
                if isinstance(ln, dict):
                    ums = ln.get("used_materials")
                    if isinstance(ums, list) and len(ums) == 0:
                        ln.pop("used_materials", None)
        if parsed_lines:
            ensure_product_master_labels(src.company_id, parsed_lines, db)
            db.flush()
            enrich_actual_lines_product_codes(src.company_id, parsed_lines, db)
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
            ensure_product_master_labels(src.company_id, lines_for_dev, db)
            db.flush()
            enrich_actual_lines_product_codes(src.company_id, lines_for_dev, db)

    # 第7条逸脱: product_code 優先・両方コード無しのときのみ label。数量・順序は見ない。
    is_dev = is_actual_deviation_from_article7(src.company_id, lines_for_dev, db)
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

    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _apply_user_classification(nu, settings)
    db.add(nu)
    db.flush()

    if "lines" in patch:
        lines = parsed_lines if parsed_lines is not None else []
        has_nonempty_line_um = any(
            isinstance(ln, dict)
            and isinstance(ln.get("used_materials"), list)
            and len(ln["used_materials"]) > 0
            for ln in lines
        )
        nu.actual_lines_json = _lines_json_dumps(lines) if lines else None
        if lines:
            nu.actual_value = sum(x["value"] for x in lines)
            if im == "logistics":
                nu.actual_work_label = _join_line_labels(lines)
                nu.actual_work_type = None
                nu.actual_item_name = None
            else:
                nu.actual_item_name = _join_line_labels(lines)
                nu.actual_work_label = None
                nu.actual_work_type = None
        else:
            nu.actual_value = None
            nu.actual_lines_json = None
            nu.actual_item_name = None
            nu.actual_work_label = None
            nu.actual_work_type = None
    else:
        nu.actual_lines_json = None
        nu.actual_value = body.actual_value
        nu.actual_work_type = _opt_str(body.actual_work_type)
        nu.actual_work_label = _opt_str(body.actual_work_label)
        nu.actual_item_name = _opt_str(body.actual_item_name)

    if is_dev:
        nu.is_article7_deviation = True
        nu.is_deviation = True
        nu.deviation_reason = deviation_reason_saved
    else:
        nu.is_article7_deviation = False
        nu.is_deviation = False
        nu.deviation_reason = None

    nu.actual_at = datetime.utcnow()

    if "actual_memo" in patch:
        nu.actual_memo = _opt_memo(patch.get("actual_memo"))
    else:
        nu.actual_memo = None

    if "lines" in patch:
        if touch_line_um or has_nonempty_line_um or ("used_materials" in patch):
            nu.used_materials_json = None
    elif "used_materials" in patch:
        nu.used_materials_json = _lines_json_dumps(um_parsed) if um_parsed else None

    if "anomaly_classification" in patch:
        ac_body = body.anomaly_classification
        ac_raw = ac_body.model_dump() if ac_body is not None else {}
        parent_a = patch["pattern_a"] if "pattern_a" in patch else None
        parent_b = patch["pattern_b"] if "pattern_b" in patch else None
        json_blob, pattern_a, pattern_b, user_pattern = build_storage_from_request(
            ac_raw,
            parent_process=parent_a,
            parent_result=parent_b,
        )
        nu.anomaly_classification_json = json_blob
        nu.pattern_a = pattern_a
        nu.pattern_b = pattern_b
        nu.user_pattern = user_pattern
    else:
        if "pattern_a" in patch:
            nu.pattern_a = patch["pattern_a"]
        if "pattern_b" in patch:
            nu.pattern_b = patch["pattern_b"]
        if "pattern_b" in patch:
            nu.user_pattern = "B" if patch.get("pattern_b") else None
        elif "user_pattern" in patch:
            _up = patch.get("user_pattern")
            nu.user_pattern = "B" if (_up is not None and str(_up).strip().upper() == "B") else None
        if "pattern_a" in patch or "pattern_b" in patch:
            pa = bool(nu.pattern_a)
            pb = bool(nu.pattern_b)
            if not pa and not pb:
                nu.anomaly_classification_json = None
            else:
                blob, pa2, pb2, up = build_storage_from_request(
                    {},
                    parent_process=pa,
                    parent_result=pb,
                )
                nu.anomaly_classification_json = blob
                nu.pattern_a = pa2
                nu.pattern_b = pb2
                nu.user_pattern = up

    if (
        getattr(nu, "planned_registered_at", None) is not None
        and nu.planned_value is not None
        and nu.actual_value is not None
    ):
        nu.diff_value = nu.actual_value - nu.planned_value
    else:
        nu.diff_value = None

    sync_planned_at_with_planned_facts(nu)
    _audit_x_save(nu, settings, f"POST /work/{unit_id}/actual", "pre_commit")
    _touch_updated(nu)
    db.commit()
    db.refresh(nu)
    _audit_x_save(nu, settings, f"POST /work/{unit_id}/actual", "post_commit")

    logger.warning(
        "[measureos.work.hook] POST /work/%s/actual committed company_id=%r actual_at=%r actual_value=%r lines_json_set=%s",
        unit_id,
        nu.company_id,
        nu.actual_at.isoformat() if nu.actual_at else None,
        nu.actual_value,
        bool(nu.actual_lines_json and str(nu.actual_lines_json).strip()),
    )

    prev_unit = _find_prev_unit(nu.company_id, nu.task_id, nu.process_id,
                                nu.user_id, nu.business_date, db)
    out = _unit_to_out_with_hint(nu, settings, db, prev_unit)
    out.update(compute_actual_revision_meta_for_unit(db, nu))
    out["next_business_date"] = str(next_business_day(nu.business_date, nu.company_id, db))
    return out


@router.post("/work/{unit_id}/planned", summary="予告を記録する")
def save_planned(
    unit_id: int,
    body: schemas.PlannedIn,
    request: Request,
    db: Session = Depends(get_db),
):
    src = db.get(models.WorkUnit, unit_id)
    if not src:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, src)
    validate_unit_company_id(db, src)
    raise_if_closed(src)
    settings = _get_or_create_settings(src.company_id, db)
    im = _norm_input_mode(settings)
    patch = body.model_dump(exclude_unset=True)

    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _apply_user_classification(nu, settings)
    db.add(nu)
    db.flush()

    if "lines" in patch:
        _backfill_stored_planned_line_ids(nu)
        raw_lines = body.lines if body.lines is not None else []
        old_parsed = _parse_lines_json(nu.planned_lines_json)
        lines, err = _strict_lines_from_body(
            list(raw_lines),
            include_due_date=True,
            include_line_id=True,
            include_product_code=True,
            include_used_materials=True,
            allow_missing_main_qty=True,
        )
        if err:
            raise HTTPException(status_code=422, detail=err)
        if lines:
            _merge_due_from_previous(lines, old_parsed)
            for ln in lines:
                if isinstance(ln, dict):
                    ln.pop("line_memo", None)
                    ums = ln.get("used_materials")
                    if isinstance(ums, list) and len(ums) == 0:
                        ln.pop("used_materials", None)
            nu.planned_lines_json = _lines_json_dumps(lines)
            nu.planned_value = _sum_line_values_optional(lines)
            if im == "logistics":
                nu.planned_work_label = _join_line_labels(lines)
                nu.planned_work_type = None
                nu.planned_item_name = None
            else:
                nu.planned_item_name = _join_line_labels(lines)
                nu.planned_work_label = None
                nu.planned_work_type = None
        else:
            # Package A: 予告内容未定でも planned_registered_at でフェーズ通過を記録
            nu.planned_value = None
            nu.planned_lines_json = None
            nu.planned_item_name = None
            nu.planned_work_label = None
            nu.planned_work_type = None
    else:
        nu.planned_lines_json = None
        nu.planned_value = body.planned_value
        nu.planned_work_type = _opt_str(body.planned_work_type)
        nu.planned_work_label = _opt_str(body.planned_work_label)
        nu.planned_item_name = _opt_str(body.planned_item_name)

    nu.planned_registered_at = datetime.utcnow()

    if nu.planned_value is not None and nu.actual_value is not None:
        nu.diff_value = nu.actual_value - nu.planned_value

    sync_planned_at_with_planned_facts(nu)
    _touch_updated(nu)
    db.commit()
    db.refresh(nu)

    prev_unit = _find_prev_unit(nu.company_id, nu.task_id, nu.process_id,
                                nu.user_id, nu.business_date, db)
    return _unit_to_out_with_hint(nu, settings, db, prev_unit)


@router.post(
    "/work/{unit_id}/planned-due",
    summary="Merge due_date onto planned lines only (Article 7; match line_id)",
)
def merge_planned_due(
    unit_id: int,
    body: schemas.PlannedDueMergeIn,
    request: Request,
    db: Session = Depends(get_db),
):
    src = db.get(models.WorkUnit, unit_id)
    if not src:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, src)
    validate_unit_company_id(db, src)
    raise_if_closed(src)
    settings = _get_or_create_settings(src.company_id, db)

    rows = _parse_lines_json(getattr(src, "planned_lines_json", None))
    if not rows:
        raise HTTPException(status_code=400, detail="予告行がありません")
    base = copy.deepcopy(rows)
    _assign_missing_line_ids_mutate(base)

    if not body.entries:
        prev_unit = _find_prev_unit(
            src.company_id, src.task_id, src.process_id, src.user_id, src.business_date, db
        )
        return _unit_to_out_with_hint(src, settings, db, prev_unit)

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

    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _apply_user_classification(nu, settings)
    nu.planned_lines_json = _lines_json_dumps(base)
    db.add(nu)
    db.flush()
    sync_planned_at_with_planned_facts(nu)
    _touch_updated(nu)
    db.commit()
    db.refresh(nu)
    prev_unit = _find_prev_unit(
        nu.company_id, nu.task_id, nu.process_id, nu.user_id, nu.business_date, db
    )
    return _unit_to_out_with_hint(nu, settings, db, prev_unit)


@router.post(
    "/work/recalc-missing-boundary",
    summary="過去営業日の is_missing 再計算（cron・境界後のバッチ用）",
)
def recalc_missing_boundary(
    request: Request,
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    append-only 方針のため無効化。派生フラグは読み取り時に算出する。
    """
    if company_id is not None and str(company_id).strip():
        cid = _guard_company_session(request, company_id)
        validate_company_id(db, cid)
    logger.info(
        "[measureos.work.recalc_missing_boundary] skipped append_only company_id=%r",
        company_id,
    )
    return {
        "ok": True,
        "skipped": True,
        "reason": "append_only_derived_at_read",
        "company_id": (str(company_id).strip() if company_id and str(company_id).strip() else None),
        "units_scanned": 0,
    }


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
    未入力・営業日跨ぎのテスト用。business_date のみ別スナップショットとして INSERT する。
    """
    src = db.get(models.WorkUnit, body.id)
    if not src:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    validate_unit_company_id(db, src)
    raise_if_closed(src)
    try:
        new_d = date_type.fromisoformat(body.business_date.strip())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="business_date は YYYY-MM-DD 形式で指定してください",
        )

    settings = _get_or_create_settings(src.company_id, db)

    nu = clone_work_unit_row(src)
    strip_derived_columns_for_fact_snapshot(nu)
    _apply_user_classification(nu, settings)
    nu.business_date = new_d
    db.add(nu)
    db.flush()

    sync_planned_at_with_planned_facts(nu)
    _touch_updated(nu)
    db.commit()
    db.refresh(nu)

    prev_unit = _find_prev_unit(
        nu.company_id,
        nu.task_id,
        nu.process_id,
        nu.user_id,
        nu.business_date,
        db,
    )
    return _unit_to_out_with_hint(nu, settings, db, prev_unit)


@router.get("/work/list", summary="作業記録の一覧を取得する")
def list_work(
    request: Request,
    company_id: str,
    hide_office_closed_sources: bool = Query(
        False,
        description="true のとき、事務完了済みとして記録された peer の work_unit を一覧から除外（debug は省略）",
    ),
    trace_unit_id: Optional[int] = Query(
        None,
        description="デバッグ: この id の unit をコミット後に DB 再読込し、一覧レスポンスと併せて追跡ログする",
    ),
    db: Session = Depends(get_db),
):
    cid = _guard_company_session(request, company_id)
    settings = _get_or_create_settings(cid, db)

    promote_blue_to_red_after_judgement(cid, db)

    dirty_n = len(db.dirty)
    commit_called = False
    if dirty_n > 0:
        db.commit()
        commit_called = True
    logger.info(
        "[measureos.work.list_promote_done] company_id=%r session_dirty_before_commit=%s commit_called=%s",
        company_id,
        dirty_n,
        commit_called,
    )

    sort_key = func.coalesce(models.WorkUnit.updated_at, models.WorkUnit.created_at)
    base_q = db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid)
    if hide_office_closed_sources:
        suppressed_sq = db.query(models.OfficeClosedWorkUnitSuppress.peer_unit_id)
        base_q = base_q.filter(~models.WorkUnit.id.in_(suppressed_sq))
    units = (
        base_q.order_by(sort_key.desc().nulls_last(), models.WorkUnit.id.desc())
        .limit(200)
        .all()
    )
    rev_meta = enrich_units_actual_revision_meta(units, db)
    out = []
    for u in units:
        row = _unit_to_out(u, settings, db, None, office_chain_hint="")
        row.update(rev_meta.get(u.id, {}))
        out.append(row)
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


@router.patch(
    "/work/{unit_id}/reflection",
    summary="【事務】反映判断のみ更新（採用／却下／未確定に戻す）",
)
def patch_office_reflection(
    unit_id: int,
    body: schemas.OfficeReflectionPatch,
    request: Request,
    db: Session = Depends(get_db),
):
    unit = db.get(models.WorkUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="作業記録が見つかりません")
    _guard_unit_session(request, unit)
    validate_unit_company_id(db, unit)
    raise_if_closed(unit)

    rs = body.reflection_status
    if rs == "rejected":
        code = (body.reject_reason_code or "").strip()
        if code not in ("input_error", "outside_instruction", "other"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "却下時は reject_reason_code が必要です "
                    "（input_error | outside_instruction | other）"
                ),
            )
        detail_txt = (body.reject_reason_detail or "").strip()
        if code == "other" and not detail_txt:
            raise HTTPException(
                status_code=422,
                detail="理由が「その他」のときは reject_reason_detail を入力してください",
            )
        unit.reflection_status = "rejected"
        unit.reflection_reject_reason_code = code
        unit.reflection_reject_reason_detail = detail_txt if code == "other" else None
    elif rs == "accepted":
        unit.reflection_status = "accepted"
        unit.reflection_reject_reason_code = None
        unit.reflection_reject_reason_detail = None
    else:
        unit.reflection_status = "pending"
        unit.reflection_reject_reason_code = None
        unit.reflection_reject_reason_detail = None

    _touch_updated(unit)
    db.commit()
    db.refresh(unit)
    settings = _get_or_create_settings(unit.company_id, db)
    prev_unit = _find_prev_unit(
        unit.company_id,
        unit.task_id,
        unit.process_id,
        unit.user_id,
        unit.business_date,
        db,
    )
    return _unit_to_out_with_hint(unit, settings, db, prev_unit)
