"""第7条一覧向け: 第5条（WorkUnit 実績）から注意・ヒント・（現場向け）進捗数量を付与する。

第7条（PriorityItem）の数量・status・行自体は一切更新しない。表示用メタデータのみ。
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.article7_safety_stock import load_safety_stock_by_product_code
from app.services.business_date import calc_business_date_with_db, nearest_workday

_MAX_NOTICES = 3

_PROGRESS_EPS = 1e-9

logger = logging.getLogger(__name__)

_ARTICLE5_PROGRESS_DEBUG = os.environ.get("MEASUREOS_ARTICLE5_PROGRESS_DEBUG", "").strip() in (
    "1",
    "true",
    "yes",
)

_NOTICE_TODAY = "※本日この商品に実績入力があります"
_NOTICE_RECENT = "※直近で製造実績があります"
_NOTICE_UNREFLECTED = "※既存システム未反映の可能性があります"
_NOTICE_CONTRADICTION = "※不足数と実績に差異があります（再確認）"


def _opt_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def _parse_actual_lines_json(raw: Optional[str]) -> List[dict]:
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
            row: dict = {"label": lb, "value": fv}
            pc_line = str(it.get("product_code", "")).strip()
            if pc_line:
                row["product_code"] = pc_line
            out.append(row)
    return out


def _actual_lines_resolved(unit: models.WorkUnit, im: str) -> List[dict]:
    parsed = _parse_actual_lines_json(getattr(unit, "actual_lines_json", None))
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


def _line_belongs_to_priority(line: dict, p: models.PriorityItem) -> bool:
    """1) 両方 product_code あり → コード一致のみ。2) 両方なし → label のみ一致。3) 片方だけコードあり → 不一致（結合しない）。"""
    pl_pc = (p.product_code or "").strip()
    pl_lb = (p.label or "").strip()
    ln_pc = str(line.get("product_code") or "").strip()
    ln_lb = str(line.get("label") or "").strip()
    has_pl_pc = bool(pl_pc)
    has_ln_pc = bool(ln_pc)
    if has_pl_pc and has_ln_pc:
        return pl_pc == ln_pc
    if not has_pl_pc and not has_ln_pc:
        return ln_lb == pl_lb and ln_lb != ""
    return False


def _previous_business_day(bd: date, company_id: str, db: Session) -> date:
    return nearest_workday(bd - timedelta(days=1), company_id, db, direction="prev")


def _settings_ephemeral(company_id: str, db: Session) -> models.CompanySettings:
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if s:
        return s
    from datetime import time as time_type

    return models.CompanySettings(
        company_id=company_id,
        unit="個",
        tolerance_value=0,
        day_boundary_time=time_type(0, 0),
        package_code="A",
    )


def _norm_input_mode(settings: models.CompanySettings) -> str:
    im = (settings.input_mode or "manufacturing").strip()
    return im if im else "manufacturing"


def _fmt_qty(x: float) -> str:
    if not math.isfinite(x):
        return "0"
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return str(round(x, 2))


def _work_unit_has_positive_actual_content(unit: models.WorkUnit, im: str) -> bool:
    """actual_at 付きでも数量ゼロの行は進捗集計対象外。"""
    if getattr(unit, "actual_at", None) is None:
        return False
    for line in _actual_lines_resolved(unit, im):
        try:
            v = float(line.get("value", 0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            return True
    return False


def _unit_has_matching_positive_actual(unit: models.WorkUnit, p: models.PriorityItem, im: str) -> bool:
    if not _work_unit_has_positive_actual_content(unit, im):
        return False
    for line in _actual_lines_resolved(unit, im):
        if not _line_belongs_to_priority(line, p):
            continue
        try:
            v = float(line.get("value", 0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            return True
    return False


def _sum_actuals_all_finalized(
    units: List[models.WorkUnit],
    p: models.PriorityItem,
    im: str,
) -> float:
    """与えられた WorkUnit 行について、actual_at がある行のラインを PriorityItem に突合し数量を合算する。"""
    total = 0.0
    for u in units:
        if getattr(u, "actual_at", None) is None:
            continue
        for line in _actual_lines_resolved(u, im):
            if not _line_belongs_to_priority(line, p):
                continue
            try:
                v = float(line.get("value", 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(v) and v > 0:
                total += v
    return total


def _latest_work_units_with_actual_per_natural_key(
    units: List[models.WorkUnit],
    im: str,
) -> List[models.WorkUnit]:
    """
    同一 (company_id, task_id, process_id, user_id, business_date) について、
    数量のある実績（actual_lines または actual_value > 0）のうち id 最大だけを採用する。
    actual_at のみで内容が空の行は進捗集計対象外（監査・異常判定用には残る）。
    business_date が無い行はキー无法のためそのまま1件ずつ含める。
    """
    by_natural: Dict[Tuple[str, str, str, str, date], List[models.WorkUnit]] = defaultdict(list)
    loose: List[models.WorkUnit] = []
    for u in units:
        if not _work_unit_has_positive_actual_content(u, im):
            continue
        bd = u.business_date
        if bd is None:
            loose.append(u)
            continue
        by_natural[
            (u.company_id, u.task_id, u.process_id, u.user_id, bd)
        ].append(u)
    out: List[models.WorkUnit] = list(loose)
    for lst in by_natural.values():
        out.append(max(lst, key=lambda x: x.id))
    return out


def _progress_session_key(unit: models.WorkUnit) -> Tuple:
    """
    製造セッションキー。planned_registered_at あり → 予告登録単位。
    無い行（テスト・レガシー）は natural key 単位で訂正最新1件にフォールバック。
    """
    preg = getattr(unit, "planned_registered_at", None)
    if preg is not None:
        return ("preg", preg)
    bd = unit.business_date
    if bd is None:
        return ("loose", int(unit.id))
    return (
        "nk",
        unit.company_id,
        unit.task_id,
        unit.process_id,
        unit.user_id,
        bd,
    )


def _latest_work_units_with_actual_for_priority(
    units: List[models.WorkUnit],
    p: models.PriorityItem,
    im: str,
) -> List[models.WorkUnit]:
    """
    planned_registered_at ごとの製造セッションについて、当該 PriorityItem に突合する
    数量あり実績を含む WorkUnit のうち id 最大を1件採用し、セッション間は合算する。
    同一セッション内の save_actual 訂正（clone 連鎖）は最新 id のみ残る。
    """
    by_session: Dict[Tuple, List[models.WorkUnit]] = defaultdict(list)
    for u in units:
        if not _unit_has_matching_positive_actual(u, p, im):
            continue
        by_session[_progress_session_key(u)].append(u)
    out: List[models.WorkUnit] = []
    for lst in by_session.values():
        out.append(max(lst, key=lambda x: x.id))
    return out


def _matching_qty_on_unit(unit: models.WorkUnit, p: models.PriorityItem, im: str) -> float:
    total = 0.0
    for line in _actual_lines_resolved(unit, im):
        if not _line_belongs_to_priority(line, p):
            continue
        try:
            v = float(line.get("value", 0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            total += v
    return total


def _log_article5_progress_debug(
    p: models.PriorityItem,
    all_units: List[models.WorkUnit],
    picked_units: List[models.WorkUnit],
    im: str,
    completed: float,
) -> None:
    if not _ARTICLE5_PROGRESS_DEBUG:
        return
    candidates: List[models.WorkUnit] = []
    for u in all_units:
        if getattr(u, "actual_at", None) is None:
            continue
        if _matching_qty_on_unit(u, p, im) <= _PROGRESS_EPS:
            continue
        candidates.append(u)
    candidates.sort(key=lambda x: x.id)

    by_session: Dict[Tuple, List[models.WorkUnit]] = defaultdict(list)
    for u in candidates:
        by_session[_progress_session_key(u)].append(u)

    session_bits: List[str] = []
    picked_ids = {int(u.id) for u in picked_units}
    for sk, lst in sorted(by_session.items(), key=lambda kv: str(kv[0])):
        lst_sorted = sorted(lst, key=lambda x: x.id)
        picked = max(lst_sorted, key=lambda x: x.id)
        preg = getattr(picked, "planned_registered_at", None)
        session_bits.append(
            f"session_key={sk!r} planned_registered_at={preg!r} "
            f"candidates={[u.id for u in lst_sorted]} "
            f"picked_unit_id={picked.id} picked_qty={_matching_qty_on_unit(picked, p, im)}"
        )

    sum_bits: List[str] = []
    for u in sorted(picked_units, key=lambda x: x.id):
        qty = _matching_qty_on_unit(u, p, im)
        sum_bits.append(
            f"unit_id={u.id} planned_reg={getattr(u, 'planned_registered_at', None)!r} "
            f"qty={qty}"
        )

    logger.info(
        "article5_progress priority_id=%s product_code=%r label=%r prod_value=%s "
        "sessions=[%s] picked_for_sum=[%s] completed_qty=%s",
        p.id,
        (p.product_code or "").strip(),
        (p.label or "").strip(),
        p.prod_value,
        " | ".join(session_bits) if session_bits else "(none)",
        " | ".join(sum_bits) if sum_bits else "(none)",
        completed,
    )


@dataclass(frozen=True)
class Article5ProgressRow:
    """第5条実績を第7条表示に接続する参考数量（priority_item / prod_value は変更しない）。"""

    completed_qty: float
    remaining_qty: float
    effective_usable_qty: float
    margin_after_ship_qty: float


def article5_progress_for_priority_items(
    company_id: str,
    priorities: List[models.PriorityItem],
    db: Session,
) -> Dict[int, Article5ProgressRow]:
    """
    priority.id -> Article5ProgressRow。
    completed は planned_registered_at セッションごとに最新実績1件を採用し、セッション間合算する。
    remaining_qty = max(0, prod_value - completed_qty)（現場向け製造残）。
    effective_usable_qty = stock_qty + completed_qty（在庫CSV + 作成済み）。
    margin_after_ship_qty = effective_usable_qty - ship_value - safety_stock（基準在庫を残した出荷後余裕）。
    PriorityItem は更新しない。
    """
    cid = (company_id or "").strip()
    out: Dict[int, Article5ProgressRow] = {}
    if not cid or not priorities:
        return out

    settings = _settings_ephemeral(cid, db)
    im = _norm_input_mode(settings)
    safety_map = load_safety_stock_by_product_code(db, cid)

    units = (
        db.query(models.WorkUnit)
        .filter(models.WorkUnit.company_id == cid)
        .filter(models.WorkUnit.actual_at.isnot(None))
        .all()
    )

    for p in priorities:
        picked_units = _latest_work_units_with_actual_for_priority(units, p, im)
        completed = _sum_actuals_all_finalized(picked_units, p, im)
        _log_article5_progress_debug(p, units, picked_units, im, completed)
        prod = float(p.prod_value) if p.prod_value is not None else 0.0
        if not math.isfinite(prod) or prod < 0:
            prod = 0.0
        remaining = max(0.0, prod - completed)
        if not math.isfinite(remaining):
            remaining = prod

        stock = float(getattr(p, "stock_qty", None) or 0)
        if not math.isfinite(stock) or stock < 0:
            stock = 0.0
        effective_usable = stock + completed
        if not math.isfinite(effective_usable):
            effective_usable = stock

        ship = float(p.ship_value) if p.ship_value is not None else 0.0
        if not math.isfinite(ship) or ship < 0:
            ship = 0.0
        pc = (getattr(p, "product_code", None) or "").strip()
        sinfo = safety_map.get(pc)
        safety = float(sinfo.value) if sinfo else 0.0
        if not math.isfinite(safety) or safety < 0:
            safety = 0.0

        margin = effective_usable - ship - safety
        if not math.isfinite(margin):
            margin = effective_usable - ship - safety

        out[int(p.id)] = Article5ProgressRow(
            completed_qty=completed,
            remaining_qty=remaining,
            effective_usable_qty=effective_usable,
            margin_after_ship_qty=margin,
        )

    return out


def _sum_actuals_for_priority(
    units: List[models.WorkUnit],
    p: models.PriorityItem,
    im: str,
    dates: Set[date],
) -> float:
    total = 0.0
    for u in units:
        bd = u.business_date
        if bd is None or bd not in dates:
            continue
        for line in _actual_lines_resolved(u, im):
            if not _line_belongs_to_priority(line, p):
                continue
            try:
                v = float(line.get("value", 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(v) and v > 0:
                total += v
    return total


def article7_context_for_priority_items(
    company_id: str,
    priorities: List[models.PriorityItem],
    db: Session,
) -> Dict[int, Tuple[Optional[str], List[str]]]:
    """
    priority.id -> (article7_actual_hint, article7_notices)
    notices は最大 _MAX_NOTICES 件。表示優先度: ④→①→③→②
    """
    cid = (company_id or "").strip()
    out: Dict[int, Tuple[Optional[str], List[str]]] = {}
    if not cid or not priorities:
        return out

    settings = _settings_ephemeral(cid, db)
    im = _norm_input_mode(settings)
    unit_label = (settings.unit or "個").strip() or "個"

    today_biz = calc_business_date_with_db(datetime.utcnow(), settings, db)
    prev1 = _previous_business_day(today_biz, cid, db)
    prev2 = _previous_business_day(prev1, cid, db)

    today_dates: Set[date] = {today_biz}
    recent_dates: Set[date] = {prev1, prev2}
    window_dates: Set[date] = {today_biz, prev1, prev2}

    units = (
        db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid).all()
    )
    by_natural: Dict[Tuple[str, str, str, str, date], List[models.WorkUnit]] = defaultdict(list)
    for u in units:
        bd = u.business_date
        if bd is None:
            continue
        by_natural[(u.company_id, u.task_id, u.process_id, u.user_id, bd)].append(u)
    latest_snapshots = [max(lst, key=lambda x: x.id) for lst in by_natural.values()]

    for p in priorities:
        today_sum = _sum_actuals_for_priority(latest_snapshots, p, im, today_dates)
        recent_only_sum = _sum_actuals_for_priority(latest_snapshots, p, im, recent_dates)
        window_sum = _sum_actuals_for_priority(latest_snapshots, p, im, window_dates)

        eps = 1e-9
        has_window = window_sum > eps
        prod = float(p.prod_value) if p.prod_value is not None else 0.0

        if today_sum > eps:
            hint: Optional[str] = f"本日実績：{_fmt_qty(today_sum)}{unit_label}"
        elif recent_only_sum > eps:
            hint = "直近実績あり"
        else:
            hint = None

        notices: List[str] = []
        if prod > eps and window_sum + eps >= prod:
            notices.append(_NOTICE_CONTRADICTION)
        if today_sum > eps:
            notices.append(_NOTICE_TODAY)
        if prod > eps and has_window:
            notices.append(_NOTICE_UNREFLECTED)
        if recent_only_sum > eps:
            notices.append(_NOTICE_RECENT)

        notices = notices[:_MAX_NOTICES]
        out[int(p.id)] = (hint, notices)

    return out
