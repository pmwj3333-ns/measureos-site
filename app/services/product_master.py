"""商品マスタ: 第5条実績の product_code 補完・ラベル自動登録。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set

from sqlalchemy.orm import Session

from app import models


def _strip_opt(s) -> str:
    if s is None:
        return ""
    return str(s).strip()


def ensure_product_master_labels(company_id: str, lines: List[dict], db: Session) -> None:
    """各実績行の label で ProductMaster が無ければ product_code=null で作成する。"""
    cid = _strip_opt(company_id)
    if not cid or not lines:
        return
    seen: Set[str] = set()
    now = datetime.utcnow()
    for row in lines:
        lb = _strip_opt(row.get("label"))
        if not lb or lb in seen:
            continue
        seen.add(lb)
        exists = (
            db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == cid)
            .filter(models.ProductMaster.label == lb)
            .first()
        )
        if exists:
            continue
        db.add(
            models.ProductMaster(
                company_id=cid,
                label=lb,
                product_code=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )


def enrich_actual_lines_product_codes(company_id: str, lines: List[dict], db: Session) -> None:
    """
    product_code が空の行に、マスタ→第7条 open の順で一意に決まるコードを付与する。
    同一 label に複数コードがある第7条行がある場合は付与しない（誤結合防止）。
    """
    cid = _strip_opt(company_id)
    if not cid or not lines:
        return

    masters = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .filter(models.ProductMaster.is_active.is_(True))
        .order_by(models.ProductMaster.id.asc())
        .all()
    )
    master_code: Dict[str, str] = {}
    for m in masters:
        lb = _strip_opt(m.label)
        pc = _strip_opt(m.product_code)
        if not lb or not pc:
            continue
        if lb not in master_code:
            master_code[lb] = pc

    pri_rows = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .filter(models.PriorityItem.status == "open")
        .all()
    )
    pri_codes_by_label: Dict[str, Set[str]] = defaultdict(set)
    for p in pri_rows:
        lb = _strip_opt(p.label)
        pc = _strip_opt(p.product_code)
        if lb and pc:
            pri_codes_by_label[lb].add(pc)

    for row in lines:
        if _strip_opt(row.get("product_code")):
            continue
        lb = _strip_opt(row.get("label"))
        if not lb:
            continue
        if lb in master_code:
            row["product_code"] = master_code[lb]
            continue
        codes = pri_codes_by_label.get(lb) or set()
        if len(codes) == 1:
            row["product_code"] = next(iter(codes))
