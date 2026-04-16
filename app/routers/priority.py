"""第7条フェーズ1: 現場履歴と独立した優先指示（priority_item）。"""

import math
from datetime import date as date_type, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import PriorityItemIn, PriorityItemOut, PriorityItemsCreateIn, PriorityItemsOut

router = APIRouter(prefix="/v2/priority", tags=["v2-第7条"])


def _norm_due_date(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        d = date_type.fromisoformat(s)
    except ValueError:
        return None
    return d.isoformat()


def _rows_to_out(rows: List[models.PriorityItem]) -> List[PriorityItemOut]:
    return [
        PriorityItemOut(
            id=r.id,
            label=r.label or "",
            ship_value=float(r.ship_value),
            prod_value=float(r.prod_value),
            due_date=r.due_date,
        )
        for r in rows
    ]


@router.get("/items", summary="第7条・優先指示一覧（会社単位）")
def list_priority_items(
    company_id: str = Query(..., description="company_id"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    rows = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .order_by(models.PriorityItem.id.asc())
        .all()
    )
    return PriorityItemsOut(items=_rows_to_out(rows))


@router.post("/create", summary="第7条・優先指示を保存（全置換）")
def create_priority_items(body: PriorityItemsCreateIn, db: Session = Depends(get_db)):
    cid = (body.company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    to_insert: List[dict] = []
    for it in body.items:
        lb = (it.label or "").strip()
        if not lb:
            continue
        try:
            ship = float(it.ship_value)
            prod = float(it.prod_value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail=f"出荷数・製造数の形式が不正です: {it.label!r}",
            )
        if not math.isfinite(ship) or not math.isfinite(prod):
            raise HTTPException(status_code=422, detail=f"出荷数・製造数が不正です: {it.label!r}")
        if prod > ship:
            raise HTTPException(
                status_code=422,
                detail=f"製造数は出荷数以下にしてください: {it.label!r}（出荷 {ship} / 製造 {prod}）",
            )
        raw_due = it.due_date
        due_out: Optional[str] = None
        if raw_due is not None and str(raw_due).strip():
            nd = _norm_due_date(str(raw_due).strip())
            if nd is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"due_date は YYYY-MM-DD で指定してください: {it.label!r}",
                )
            due_out = nd
        to_insert.append({"label": lb, "ship_value": ship, "prod_value": prod, "due_date": due_out})

    now = datetime.utcnow()
    db.query(models.PriorityItem).filter(models.PriorityItem.company_id == cid).delete(
        synchronize_session=False
    )
    for row in to_insert:
        ship = float(row["ship_value"])
        db.add(
            models.PriorityItem(
                company_id=cid,
                label=row["label"],
                ship_value=ship,
                prod_value=float(row["prod_value"]),
                value=ship,
                due_date=row["due_date"],
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    rows = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .order_by(models.PriorityItem.id.asc())
        .all()
    )
    return PriorityItemsOut(items=_rows_to_out(rows))
