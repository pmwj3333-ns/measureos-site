"""company_master 管理 API（第1段階・認証なし・全 API への company_id 検証は未接続）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import CompanyMasterCreateIn, CompanyMasterOut, CompanyMasterPatchIn

router = APIRouter(prefix="/admin/companies", tags=["admin-会社マスタ"])


def _normalize_company_id(raw: str) -> str:
    return (raw or "").strip()


def _normalize_company_name(raw: str) -> str:
    return (raw or "").strip()


def _row_to_out(r: models.CompanyMaster) -> CompanyMasterOut:
    return CompanyMasterOut(
        id=int(r.id),
        company_id=r.company_id or "",
        company_name=r.company_name or "",
        is_active=bool(getattr(r, "is_active", True)),
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


@router.get("", summary="会社マスタ一覧")
def list_companies(
    active_only: bool = Query(False, description="true のとき is_active のみ"),
    db: Session = Depends(get_db),
):
    q = db.query(models.CompanyMaster)
    if active_only:
        q = q.filter(models.CompanyMaster.is_active.is_(True))
    rows = q.order_by(
        models.CompanyMaster.company_id.asc(),
        models.CompanyMaster.id.asc(),
    ).all()
    return [_row_to_out(r) for r in rows]


@router.post("", summary="会社マスタ新規登録")
def create_company(body: CompanyMasterCreateIn, db: Session = Depends(get_db)):
    cid = _normalize_company_id(body.company_id)
    cname = _normalize_company_name(body.company_name)
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    if not cname:
        raise HTTPException(status_code=422, detail="company_name が空です")
    clash = (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == cid)
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=422,
            detail="同じ company_id が既に登録されています",
        )
    now = datetime.utcnow()
    row = models.CompanyMaster(
        company_id=cid,
        company_name=cname,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="同じ company_id が既に登録されています",
        ) from None
    db.refresh(row)
    return _row_to_out(row)


@router.patch("/{row_id}", summary="会社マスタ更新（表示名・有効フラグ）")
def patch_company(
    row_id: int,
    body: CompanyMasterPatchIn,
    db: Session = Depends(get_db),
):
    row = db.get(models.CompanyMaster, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="会社マスタが見つかりません")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return _row_to_out(row)

    if "company_name" in patch:
        cname = _normalize_company_name(patch["company_name"] or "")
        if not cname:
            raise HTTPException(status_code=422, detail="company_name が空です")
        row.company_name = cname

    if "is_active" in patch and patch["is_active"] is not None:
        row.is_active = bool(patch["is_active"])

    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _row_to_out(row)
