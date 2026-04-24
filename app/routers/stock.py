"""第7条ステップ①: 在庫CSV取り込み（会社単位・全置換）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import StockImportOut
from app.services.stock_csv import dedupe_by_product_code, parse_stock_csv_text

router = APIRouter(prefix="/v2/stock", tags=["v2-在庫"])


def _decode_upload(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


@router.post("/import", summary="在庫CSV取り込み（会社単位・全置換）")
async def import_stock_csv(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")

    raw = await file.read()
    text = _decode_upload(raw)
    rows, row_err_count, fatal = parse_stock_csv_text(text)
    if fatal:
        raise HTTPException(status_code=422, detail=fatal)

    rows_deduped = dedupe_by_product_code(rows)
    success_count = len(rows_deduped)
    now = datetime.utcnow()

    try:
        db.query(models.StockItem).filter(models.StockItem.company_id == cid).delete(
            synchronize_session=False
        )
        for r in rows_deduped:
            db.add(
                models.StockItem(
                    company_id=cid,
                    product_code=r["product_code"],
                    label=r["label"],
                    stock_qty=float(r["stock_qty"]),
                    safety_stock=r["safety_stock"],
                    created_at=now,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return StockImportOut(
        ok=True,
        success_count=success_count,
        error_count=row_err_count,
    )
