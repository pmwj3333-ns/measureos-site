"""第7条ステップ②: 出荷予定CSV取り込み（会社単位・全置換）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import ShipmentImportOut
from app.services.shipment_csv import dedupe_by_product_code_and_due_date, parse_shipment_csv_text

router = APIRouter(prefix="/v2/shipment", tags=["v2-出荷予定"])


def _decode_upload(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


@router.post("/import", summary="出荷予定CSV取り込み（会社単位・全置換）")
async def import_shipment_csv(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")

    raw = await file.read()
    text = _decode_upload(raw)
    rows, row_err_count, fatal = parse_shipment_csv_text(text)
    if fatal:
        raise HTTPException(status_code=422, detail=fatal)

    rows_deduped = dedupe_by_product_code_and_due_date(rows)
    success_count = len(rows_deduped)
    now = datetime.utcnow()

    try:
        db.query(models.ShipmentPlanItem).filter(
            models.ShipmentPlanItem.company_id == cid
        ).delete(synchronize_session=False)
        for r in rows_deduped:
            db.add(
                models.ShipmentPlanItem(
                    company_id=cid,
                    product_code=r["product_code"],
                    label=r["label"],
                    ship_qty=float(r["ship_qty"]),
                    due_date=r["due_date"],
                    ordered_at=r.get("ordered_at"),
                    created_at=now,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return ShipmentImportOut(
        ok=True,
        success_count=success_count,
        error_count=row_err_count,
    )
