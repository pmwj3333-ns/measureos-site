"""第7条フェーズ1: 事務（OS）が登録する「何を・どれだけ・いつ」等の指示（priority_item）。第5条の現場記録とは独立。"""

import math
from datetime import date as date_type, datetime
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import (
    PriorityCloseIn,
    PriorityCloseOut,
    PriorityItemIn,
    PriorityItemOut,
    PriorityItemsCreateIn,
    PriorityItemsOut,
    PriorityRebuildIn,
    PriorityRebuildOut,
)
from app.services.article7_priority_phase1 import compute_article7_priority_phase1
from app.services.priority_article7_context import article7_context_for_priority_items
from app.services.priority_rebuild import rebuild_priority_items_for_company

router = APIRouter(prefix="/v2/priority", tags=["v2-第7条"])


def _priority_rank(level: str) -> int:
    s = (level or "").strip().lower()
    if s == "high":
        return 0
    if s == "mid":
        return 1
    return 2


def _priority_tuple_for_row(r: models.PriorityItem) -> Tuple[str, float]:
    pl, sc = compute_article7_priority_phase1(
        r.ship_value,
        getattr(r, "stock_qty", None) or 0,
        r.due_date,
    )
    return pl, float(sc)


def _priority_sort_key(rr: models.PriorityItem) -> Tuple[int, str, int]:
    pl, _ = _priority_tuple_for_row(rr)
    due_s = str(rr.due_date or "").strip() or "9999-12-31"
    return (_priority_rank(pl), due_s, int(rr.id))


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


def _rows_to_out(
    rows: List[models.PriorityItem],
    ctx: Optional[Dict[int, Tuple[Optional[str], List[str]]]] = None,
) -> List[PriorityItemOut]:
    ctx = ctx or {}
    items: List[PriorityItemOut] = []
    for r in rows:
        hint, notices = ctx.get(int(r.id), (None, []))
        pl, pscore = _priority_tuple_for_row(r)
        items.append(
            PriorityItemOut(
                id=r.id,
                product_code=getattr(r, "product_code", None) or "",
                label=r.label or "",
                ship_value=float(r.ship_value),
                stock_qty=float(getattr(r, "stock_qty", None) or 0),
                prod_value=float(r.prod_value),
                due_date=r.due_date,
                status=(getattr(r, "status", None) or "open").strip() or "open",
                priority_level=str(pl),
                priority_score=float(pscore),
                article7_actual_hint=hint,
                article7_notices=list(notices),
            )
        )
    return items


@router.get("/items", summary="第7条・優先指示一覧（会社単位・open のみ）")
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
        .filter(models.PriorityItem.status == "open")
        .order_by(models.PriorityItem.id.asc())
        .all()
    )

    rows_sorted = sorted(rows, key=_priority_sort_key)
    ctx = article7_context_for_priority_items(cid, rows_sorted, db)
    return PriorityItemsOut(items=_rows_to_out(rows_sorted, ctx))


@router.post(
    "/rebuild",
    summary="第7条・在庫×出荷予定から再生成（全置換・OS計算）",
)
def rebuild_priority_items(body: PriorityRebuildIn, db: Session = Depends(get_db)):
    """
    当該 company_id の **open** の priority_item のみ削除し、出荷×在庫から再生成する（closed は残す）。
    stock_qty = stock_map.get(product_code, 0)、required_qty = max(0, ship_qty - stock_qty)。
    required_qty > 0 かつ納期が parse_due_date 可能な行のみ保存する。
    """
    cid = (body.company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    success_count, warning_count, detail = rebuild_priority_items_for_company(cid, db)
    return PriorityRebuildOut(
        ok=True,
        success_count=success_count,
        warning_count=warning_count,
        detail=detail,
    )


@router.post("/close", summary="第7条・事務クローズ（open → closed）")
def close_priority_items(body: PriorityCloseIn, db: Session = Depends(get_db)):
    """第5条では数量を変えず、事務の承認操作でのみ行を閉じる。closed は GET /items に出ない。"""
    cid = (body.company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    raw_ids = [int(x) for x in body.item_ids]
    ids = list(dict.fromkeys(raw_ids))
    if not ids:
        raise HTTPException(status_code=422, detail="item_ids が空です")
    rows = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .filter(models.PriorityItem.id.in_(ids))
        .all()
    )
    found = {int(r.id) for r in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"company_id に一致する priority_item が見つかりません: id={missing}",
        )
    now = datetime.utcnow()
    n = 0
    for r in rows:
        st = (getattr(r, "status", None) or "open").strip() or "open"
        if st != "open":
            continue
        r.status = "closed"
        r.updated_at = now
        n += 1
    db.commit()
    return PriorityCloseOut(ok=True, closed_count=n)


@router.post("/create", summary="第7条・優先指示を保存（open 全置換）")
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
        stock_q = max(0.0, ship - prod)
        to_insert.append(
            {
                "label": lb,
                "ship_value": ship,
                "stock_qty": stock_q,
                "prod_value": prod,
                "due_date": due_out,
            }
        )

    now = datetime.utcnow()
    db.query(models.PriorityItem).filter(
        models.PriorityItem.company_id == cid,
        models.PriorityItem.status == "open",
    ).delete(synchronize_session=False)
    for row in to_insert:
        ship = float(row["ship_value"])
        db.add(
            models.PriorityItem(
                company_id=cid,
                product_code=str(row.get("product_code") or ""),
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
    rows = (
        db.query(models.PriorityItem)
        .filter(models.PriorityItem.company_id == cid)
        .filter(models.PriorityItem.status == "open")
        .order_by(models.PriorityItem.id.asc())
        .all()
    )

    rows_sorted = sorted(rows, key=_priority_sort_key)
    ctx = article7_context_for_priority_items(cid, rows_sorted, db)
    return PriorityItemsOut(items=_rows_to_out(rows_sorted, ctx))
