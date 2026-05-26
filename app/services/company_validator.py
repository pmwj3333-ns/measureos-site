"""company_master による company_id 入口統制（第1条）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Set

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models


def normalize_company_id(raw: Optional[str]) -> str:
    return (raw or "").strip()


def validate_company_id(db: Session, company_id: Optional[str]) -> str:
    """
    登録済みかつ有効な company_id のみ許可する。
    返値は trim 済み company_id。未登録は 422、無効は 403。
    """
    cid = normalize_company_id(company_id)
    if not cid:
        raise HTTPException(status_code=422, detail="company_id is not registered")
    row = (
        db.query(models.CompanyMaster)
        .filter(models.CompanyMaster.company_id == cid)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=422, detail="company_id is not registered")
    if not bool(getattr(row, "is_active", True)):
        raise HTTPException(status_code=403, detail="company is inactive")
    return cid


def validate_unit_company_id(db: Session, unit: models.WorkUnit) -> str:
    """work_unit 行の company_id を検証する。"""
    return validate_company_id(db, getattr(unit, "company_id", None))


def _collect_legacy_company_ids(db: Session) -> Set[str]:
    ids: Set[str] = set()

    def add_raw(raw: Optional[str]) -> None:
        s = normalize_company_id(raw)
        if s:
            ids.add(s)

    for row in db.query(models.CompanySettings.company_id).all():
        add_raw(row[0])
    for row in db.query(models.WorkUnit.company_id).distinct().all():
        add_raw(row[0])
    for row in db.query(models.ProductMaster.company_id).distinct().all():
        add_raw(row[0])
    for row in db.query(models.PriorityItem.company_id).distinct().all():
        add_raw(row[0])
    for row in db.query(models.StockItem.company_id).distinct().all():
        add_raw(row[0])
    for row in db.query(models.ShipmentPlanItem.company_id).distinct().all():
        add_raw(row[0])
    return ids


def backfill_company_master_from_legacy(db: Session) -> int:
    """
    既存テーブルに現れる company_id を company_master へ投入（未登録のみ）。
    company_settings の company_name があれば表示名に使う。
    """
    ids = _collect_legacy_company_ids(db)
    if not ids:
        return 0

    name_by_id = {
        normalize_company_id(s.company_id): (s.company_name or "").strip()
        for s in db.query(models.CompanySettings).all()
        if normalize_company_id(s.company_id)
    }
    now = datetime.utcnow()
    inserted = 0
    for cid in sorted(ids):
        if (
            db.query(models.CompanyMaster)
            .filter(models.CompanyMaster.company_id == cid)
            .first()
        ):
            continue
        cname = name_by_id.get(cid) or cid
        if not cname.strip():
            cname = cid
        db.add(
            models.CompanyMaster(
                company_id=cid,
                company_name=cname,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        inserted += 1
    if inserted:
        db.commit()
    return inserted


# pytest 等で事前登録する既知の company_id
KNOWN_TEST_COMPANY_IDS = (
    "office_v2_agg_test_co",
    "planned_reg_test_co",
    "demo_co",
    "ok_co",
)


def seed_known_test_companies(db: Session) -> None:
    """テスト DB 用: 既知 company_id を company_master に登録する。"""
    now = datetime.utcnow()
    for cid in KNOWN_TEST_COMPANY_IDS:
        if (
            db.query(models.CompanyMaster)
            .filter(models.CompanyMaster.company_id == cid)
            .first()
        ):
            continue
        db.add(
            models.CompanyMaster(
                company_id=cid,
                company_name=cid,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
