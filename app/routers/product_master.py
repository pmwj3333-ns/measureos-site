"""商品マスタ API（第5条・product_code 補完の土台・事務向け）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import (
    ProductMasterCreateIn,
    ProductMasterEnsureIn,
    ProductMasterOut,
    ProductMasterPatchIn,
)

router = APIRouter(prefix="/v2/product-master", tags=["v2-商品マスタ"])


def _row_to_out(r: models.ProductMaster) -> ProductMasterOut:
    return ProductMasterOut(
        id=int(r.id),
        company_id=r.company_id or "",
        product_code=(r.product_code or "").strip() or None,
        label=(r.label or "").strip(),
        is_active=bool(getattr(r, "is_active", True)),
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


@router.get("", summary="商品マスタ一覧（会社単位）")
def list_product_master(
    company_id: str = Query(..., description="company_id"),
    active_only: bool = Query(True, description="true のとき is_active のみ"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    q = db.query(models.ProductMaster).filter(models.ProductMaster.company_id == cid)
    if active_only:
        q = q.filter(models.ProductMaster.is_active.is_(True))
    rows = q.order_by(models.ProductMaster.label.asc(), models.ProductMaster.id.asc()).all()
    return [_row_to_out(r) for r in rows]


@router.post("", summary="商品マスタ新規作成（label のみ・同一会社で label 重複は 422）")
def create_product_master(body: ProductMasterCreateIn, db: Session = Depends(get_db)):
    cid = (body.company_id or "").strip()
    lb = (body.label or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    if not lb:
        raise HTTPException(status_code=422, detail="label が空です")
    clash = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .filter(models.ProductMaster.label == lb)
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=422,
            detail="同じ会社に既にその商品名（label）があります",
        )
    now = datetime.utcnow()
    row = models.ProductMaster(
        company_id=cid,
        label=lb,
        product_code=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_out(row)


@router.post("/ensure", summary="ラベルが無ければマスタに1件作成（product_code は null）")
def ensure_product_master(body: ProductMasterEnsureIn, db: Session = Depends(get_db)):
    cid = (body.company_id or "").strip()
    lb = (body.label or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    if not lb:
        raise HTTPException(status_code=422, detail="label が空です")
    now = datetime.utcnow()
    ex = (
        db.query(models.ProductMaster)
        .filter(models.ProductMaster.company_id == cid)
        .filter(models.ProductMaster.label == lb)
        .first()
    )
    if ex:
        return _row_to_out(ex)
    row = models.ProductMaster(
        company_id=cid,
        label=lb,
        product_code=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_out(row)


def _dup_code_error() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail="同じ会社に既にその product_code を持つ商品があります",
    )


@router.patch("/{row_id}", summary="商品マスタのコード・ラベル・有効フラグを更新")
def patch_product_master(row_id: int, body: ProductMasterPatchIn, db: Session = Depends(get_db)):
    row = db.get(models.ProductMaster, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="商品マスタが見つかりません")
    patch = body.model_dump(exclude_unset=True)
    now = datetime.utcnow()

    if "label" in patch:
        nl = (patch["label"] or "").strip()
        if not nl:
            raise HTTPException(status_code=422, detail="label が空です")
        clash = (
            db.query(models.ProductMaster)
            .filter(models.ProductMaster.company_id == row.company_id)
            .filter(models.ProductMaster.label == nl)
            .filter(models.ProductMaster.id != row_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=422, detail="同じ会社に既にその label があります")
        row.label = nl

    if "product_code" in patch:
        raw = patch["product_code"]
        if raw is None or not str(raw).strip():
            row.product_code = None
        else:
            pc = str(raw).strip()
            dup = (
                db.query(models.ProductMaster)
                .filter(models.ProductMaster.company_id == row.company_id)
                .filter(models.ProductMaster.id != row_id)
                .filter(models.ProductMaster.is_active.is_(True))
                .filter(models.ProductMaster.product_code == pc)
                .first()
            )
            if dup:
                raise _dup_code_error()
            row.product_code = pc

    if "is_active" in patch and patch["is_active"] is not None:
        row.is_active = bool(patch["is_active"])

    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _row_to_out(row)
