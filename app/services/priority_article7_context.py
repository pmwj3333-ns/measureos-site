"""第7条一覧向け: 第5条（WorkUnit 実績）から注意・実績ヒントを付与する。

第7条（PriorityItem）の数量・行自体は一切更新しない。表示用メタデータのみ。
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.business_date import calc_business_date_with_db, nearest_workday

_MAX_NOTICES = 3

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
