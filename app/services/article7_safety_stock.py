"""第7条・商品マスタの基準在庫（safety_stock_value）を優先度計算へ組み込む。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models


@dataclass(frozen=True)
class SafetyStockInfo:
    """product_code 単位の基準在庫。未設定は value=0・is_unset=True。"""

    value: int
    is_unset: bool


def normalize_safety_stock_value(raw: object) -> tuple[Optional[int], bool]:
    """
    DB 値を正規化する。
    Returns: (value_for_calc, is_unset)
    - NULL → (0, True)
    - 数値 → (max(0, int), False)
    """
    if raw is None:
        return 0, True
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0, True
    return max(0, v), False


def load_safety_stock_by_product_code(db: Session, company_id: str) -> Dict[str, SafetyStockInfo]:
    """有効な商品マスタから product_code → 基準在庫を構築（コード空はスキップ）。"""
    cid = (company_id or "").strip()
    if not cid:
        return {}
    out: Dict[str, SafetyStockInfo] = {}
    rows = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .filter(models.ProductMaster.is_active.is_(True))
        .all()
    )
    for r in rows:
        pc = (r.product_code or "").strip()
        if not pc:
            continue
        val, unset = normalize_safety_stock_value(getattr(r, "safety_stock_value", None))
        out[pc] = SafetyStockInfo(value=val, is_unset=unset)
    return out


def shortage_qty(current_stock: float, safety_stock: int, ship_qty: float) -> float:
    """available = current_stock - safety_stock - ship_qty; 不足は max(0, -available)。"""
    available = float(current_stock) - float(safety_stock) - float(ship_qty)
    return max(0.0, -available)


def usable_stock_qty(current_stock: float, safety_stock: int) -> float:
    return max(0.0, float(current_stock) - float(safety_stock))


_SHORTAGE_EPS = 1e-9


def is_manual_priority_item(product_code: str) -> bool:
    """POST /v2/priority/create 由来（product_code 空）。rebuild 行はコード必須。"""
    return not (product_code or "").strip()


def decompose_shortage_for_display(
    stock_qty: float,
    ship_value: float,
    prod_value: float,
    *,
    safety_stock_unset: bool = True,
    product_code: str = "",
) -> Tuple[float, float, List[str]]:
    """
    不足内訳（表示専用）。prod_value は変更しない。
    ship_part = max(0, ship - stock)
    safety_part = max(0, prod - ship_part)
    """
    stock = max(0.0, float(stock_qty)) if math.isfinite(float(stock_qty)) else 0.0
    ship = max(0.0, float(ship_value)) if math.isfinite(float(ship_value)) else 0.0
    prod = max(0.0, float(prod_value)) if math.isfinite(float(prod_value)) else 0.0

    if is_manual_priority_item(product_code) and prod > _SHORTAGE_EPS:
        return prod, 0.0, ["出荷不足（手入力）"]

    ship_part = max(0.0, ship - stock)
    safety_part = max(0.0, prod - ship_part)

    labels: List[str] = []
    if ship_part > _SHORTAGE_EPS:
        labels.append("出荷不足")
    if safety_part > _SHORTAGE_EPS and not safety_stock_unset:
        labels.append("基準在庫不足")

    return ship_part, safety_part, labels
