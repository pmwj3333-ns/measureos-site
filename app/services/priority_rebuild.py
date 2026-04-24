"""在庫×出荷予定から第7条（priority_item）を再生成する。

- 出荷行を走査し product_code で stock_map と突合。
- stock_qty = stock_map.get(product_code, 0)
- required_qty = max(0, ship_qty - stock_qty)
- required_qty > 0 の行のみ保存。在庫のみの商品は出荷が無いため対象外。
- due_date は parse_due_date で YYYY-MM-DD にできない行は保存せずログに出す。

削除は当該 company_id かつ status=open のみ（closed は残す。他社・全件削除は行わない）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.shipment_csv import parse_due_date

logger = logging.getLogger(__name__)


def rebuild_priority_items_for_company(company_id: str, db: Session) -> Tuple[int, int, Optional[str]]:
    """
    指定 company_id の ShipmentPlanItem を基準に priority_item を再生成する。
    既存の当該会社分のみ削除してから挿入する。
    """
    cid = (company_id or "").strip()

    stock_rows: List[models.StockItem] = (
        db.query(models.StockItem).filter(models.StockItem.company_id == cid).all()
    )
    stock_map: Dict[str, float] = {}
    for s in stock_rows:
        pc = (s.product_code or "").strip()
        if not pc:
            continue
        stock_map[pc] = float(s.stock_qty) if s.stock_qty is not None else 0.0

    shipments: List[models.ShipmentPlanItem] = (
        db.query(models.ShipmentPlanItem)
        .filter(models.ShipmentPlanItem.company_id == cid)
        .order_by(models.ShipmentPlanItem.id.asc())
        .all()
    )

    empty_product_code_count = 0
    skipped_no_need_count = 0
    skipped_bad_due_count = 0
    to_insert: List[dict] = []

    for sh in shipments:
        pc = (sh.product_code or "").strip()
        if not pc:
            empty_product_code_count += 1
            continue

        ship_qty = float(sh.ship_qty) if sh.ship_qty is not None else 0.0
        stock_qty = stock_map.get(pc, 0.0)
        required_qty = max(0.0, ship_qty - stock_qty)

        if required_qty <= 0:
            skipped_no_need_count += 1
            continue

        due_out = parse_due_date(sh.due_date)
        if not due_out:
            skipped_bad_due_count += 1
            logger.warning(
                "priority_rebuild: skip row (due_date parse failed) company_id=%r product_code=%r due_raw=%r",
                cid,
                pc,
                sh.due_date,
            )
            continue

        lb = (sh.label or "").strip() or pc
        to_insert.append(
            {
                "product_code": pc,
                "label": lb,
                "ship_value": ship_qty,
                "stock_qty": stock_qty,
                "prod_value": required_qty,
                "due_date": due_out,
            }
        )

    now = datetime.utcnow()
    try:
        # open のみ削除（closed は事務クローズとして温存）。全件・他社削除は禁止。
        deleted = (
            db.query(models.PriorityItem)
            .filter(models.PriorityItem.company_id == cid)
            .filter(models.PriorityItem.status == "open")
            .delete(synchronize_session=False)
        )
        logger.debug(
            "priority_rebuild: deleted %s priority_item rows for company_id=%r",
            deleted,
            cid,
        )

        for row in to_insert:
            ship = float(row["ship_value"])
            db.add(
                models.PriorityItem(
                    company_id=cid,
                    product_code=row["product_code"],
                    label=row["label"],
                    ship_value=ship,
                    stock_qty=float(row["stock_qty"]),
                    prod_value=float(row["prod_value"]),
                    value=ship,
                    due_date=row["due_date"],
                    status="open",
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    success_count = len(to_insert)
    warning_count = empty_product_code_count + skipped_no_need_count + skipped_bad_due_count

    parts: List[str] = []
    if empty_product_code_count > 0:
        parts.append(f"商品コード空欄の出荷行を{empty_product_code_count}件スキップしました。")
    if skipped_no_need_count > 0:
        parts.append(f"在庫で賄えるため保存しなかった出荷が{skipped_no_need_count}件ありました。")
    if skipped_bad_due_count > 0:
        parts.append(f"納期を解釈できずスキップした行が{skipped_bad_due_count}件ありました（ログ参照）。")
    detail: Optional[str] = "".join(parts) if parts else None

    return success_count, warning_count, detail
