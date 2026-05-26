"""第7条・商品マスタの基準在庫（safety_stock_value）を優先度計算へ組み込む。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

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
