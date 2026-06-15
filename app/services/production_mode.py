"""第7条・商品マスタ production_mode（製造区分）の参照。"""

from __future__ import annotations

from typing import Dict, Tuple

from sqlalchemy.orm import Session

from app import models

PRODUCTION_MODE_MANUFACTURE = "manufacture"
PRODUCTION_MODE_PURCHASE = "purchase"


def normalize_production_mode(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s == PRODUCTION_MODE_PURCHASE:
        return PRODUCTION_MODE_PURCHASE
    return PRODUCTION_MODE_MANUFACTURE


def production_mode_label(mode: str) -> str:
    if normalize_production_mode(mode) == PRODUCTION_MODE_PURCHASE:
        return "商社・仕入"
    return "自社製造"


def load_production_mode_maps(
    db: Session, company_id: str
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """product_code / label → production_mode（未設定は manufacture）。"""
    cid = (company_id or "").strip()
    by_code: Dict[str, str] = {}
    by_label: Dict[str, str] = {}
    if not cid:
        return by_code, by_label
    rows = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .all()
    )
    for r in rows:
        mode = normalize_production_mode(getattr(r, "production_mode", None))
        pc = (r.product_code or "").strip()
        lb = (r.label or "").strip()
        if pc:
            by_code[pc] = mode
        if lb:
            by_label[lb] = mode
    return by_code, by_label


def resolve_production_mode(
    product_code: object,
    label: object,
    by_code: Dict[str, str],
    by_label: Dict[str, str],
) -> str:
    pc = str(product_code or "").strip()
    if pc and pc in by_code:
        return by_code[pc]
    lb = str(label or "").strip()
    if lb and lb in by_label:
        return by_label[lb]
    return PRODUCTION_MODE_MANUFACTURE
