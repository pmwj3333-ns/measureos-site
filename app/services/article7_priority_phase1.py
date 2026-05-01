"""第7条フェーズ1・優先度（high / mid / low）。

在庫・出荷・納期から不足率と納期係数でスコアし、閾値で段階化する。
company_settings で閾値を変える拡張は未実装（定数のみ）。

ルール優先順位:
1. 納期が JST の「今日」より前なら強制 high（過去納期）
2. 不足数 shortage <= 0 なら low
3. それ以外は score = shortage_rate * due_weight で判定

shortage = max(ship_qty - stock_qty, 0)
ship_qty > 0 のとき shortage_rate = shortage / ship_qty、それ以外は 0
小数は丸めない。
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal, Optional, Tuple

from app.services.business_date import JST

PriorityLevel = Literal["high", "mid", "low"]

# 将来 company_settings 化予定の閾値（フェーズ1は固定）
_DUE_WEIGHT_LE_1 = 3
_DUE_WEIGHT_LE_3 = 2
_DUE_WEIGHT_OTHER = 1

_SCORE_HIGH = 1.5
_SCORE_MID = 0.5


def jst_today_date() -> date:
    """優先度の「今日」は JST 暦日（他条文と整合）。"""
    return datetime.now(JST).date()


def _finite_nonneg(x: object) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return max(v, 0.0)


def _parse_due_iso(raw: Optional[str]) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def compute_article7_priority_phase1(
    ship_qty: object,
    stock_qty: object,
    due_date_iso: Optional[str],
    today: Optional[date] = None,
) -> Tuple[PriorityLevel, float]:
    """
    Returns:
        (priority_level, priority_score)
        priority_score は通常ルール時は shortage_rate * due_weight。
        強制 high（過去納期）時は比較用に shortage_rate * _DUE_WEIGHT_LE_1 を返す（同日≤1 と同係数）。
        強制 low（不足なし）は 0.0。
    """
    today_d = today if today is not None else jst_today_date()
    ship = _finite_nonneg(ship_qty)
    stock = _finite_nonneg(stock_qty)
    shortage = max(ship - stock, 0.0)

    due_d = _parse_due_iso(due_date_iso)

    if due_d is not None and due_d < today_d:
        sr = (shortage / ship) if ship > 0 else 0.0
        return ("high", sr * float(_DUE_WEIGHT_LE_1))

    if shortage <= 0:
        return ("low", 0.0)

    shortage_rate = (shortage / ship) if ship > 0 else 0.0

    if due_d is None:
        due_weight = _DUE_WEIGHT_OTHER
    else:
        days_to_due = (due_d - today_d).days
        if days_to_due <= 1:
            due_weight = _DUE_WEIGHT_LE_1
        elif days_to_due <= 3:
            due_weight = _DUE_WEIGHT_LE_3
        else:
            due_weight = _DUE_WEIGHT_OTHER

    score = shortage_rate * float(due_weight)

    if score >= _SCORE_HIGH:
        level: PriorityLevel = "high"
    elif score >= _SCORE_MID:
        level = "mid"
    else:
        level = "low"

    return (level, score)
