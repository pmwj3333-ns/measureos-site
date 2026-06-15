"""商品マスタ: 第5条実績の product_code 補完・会社商品辞書（蓄積型）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.production_mode import PRODUCTION_MODE_MANUFACTURE


def _strip_opt(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _lookup_maps(
    rows: List[models.ProductMaster],
) -> Tuple[Dict[str, models.ProductMaster], Dict[str, models.ProductMaster]]:
    by_label: Dict[str, models.ProductMaster] = {}
    by_code: Dict[str, models.ProductMaster] = {}
    for r in rows:
        lb = _strip_opt(r.label)
        pc = _strip_opt(r.product_code)
        if lb and lb not in by_label:
            by_label[lb] = r
        if pc and pc not in by_code:
            by_code[pc] = r
    return by_label, by_code


def ensure_product_master_entries(
    company_id: str,
    entries: List[Mapping[str, object]],
    db: Session,
) -> int:
    """
    会社商品辞書への追加のみ（Package A: 非破壊・蓄積型）。

    - 未存在時のみ INSERT
    - 既存行は更新しない（safety_stock / production_mode 等を保持）
    - CSV に無い商品は削除しない
    """
    cid = _strip_opt(company_id)
    if not cid or not entries:
        return 0

    existing = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .all()
    )
    by_label, by_code = _lookup_maps(existing)
    seen_batch: Set[Tuple[str, str]] = set()
    now = datetime.utcnow()
    created = 0

    for raw in entries:
        pc = _strip_opt(raw.get("product_code"))
        lb = _strip_opt(raw.get("label"))
        if not pc and not lb:
            continue
        batch_key = (pc, lb or pc)
        if batch_key in seen_batch:
            continue
        seen_batch.add(batch_key)

        if pc and pc in by_code:
            continue
        use_label = lb or pc
        if use_label in by_label:
            continue

        row = models.ProductMaster(
            company_id=cid,
            label=use_label,
            product_code=pc or None,
            is_active=True,
            production_mode=PRODUCTION_MODE_MANUFACTURE,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        by_label[use_label] = row
        if pc:
            by_code[pc] = row
        created += 1

    return created


def ensure_product_master_labels(company_id: str, lines: List[dict], db: Session) -> None:
    """各実績行の label で ProductMaster が無ければ追加する（既存は触らない）。"""
    entries = [{"label": _strip_opt(row.get("label")), "product_code": ""} for row in lines]
    ensure_product_master_entries(company_id, entries, db)


def ensure_product_master_row(
    company_id: str,
    label: str,
    db: Session,
) -> models.ProductMaster:
    """label 単位の ensure（API POST /ensure 用）。既存があればそのまま返す。"""
    cid = _strip_opt(company_id)
    lb = _strip_opt(label)
    if not cid or not lb:
        raise ValueError("company_id と label が必要です")
    existing = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .filter(models.ProductMaster.label == lb)
        .first()
    )
    if existing:
        return existing
    now = datetime.utcnow()
    row = models.ProductMaster(
        company_id=cid,
        label=lb,
        product_code=None,
        is_active=True,
        production_mode=PRODUCTION_MODE_MANUFACTURE,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return row


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
