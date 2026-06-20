"""company_purge サービスのテスト。"""

from __future__ import annotations

from datetime import date, datetime

from app import models
from app.database import SessionLocal
from app.services.company_purge import (
    delete_company_and_related_data,
    plan_company_purge,
    purge_companies_except,
)


def _seed_company(cid: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            models.CompanyMaster(
                company_id=cid,
                company_name=cid,
                is_active=True,
            )
        )
        db.add(
            models.CompanySettings(
                company_id=cid,
                company_name=cid,
            )
        )
        unit = models.WorkUnit(
            company_id=cid,
            task_id="t",
            process_id="p",
            user_id="u",
            business_date=date(2026, 5, 1),
        )
        db.add(unit)
        db.flush()
        db.add(
            models.WorkUnitStatusHistory(
                work_unit_id=unit.id,
                from_status=None,
                to_status="normal",
                changed_at=datetime(2026, 5, 1, 10, 0, 0),
            )
        )
        db.add(
            models.PriorityItem(
                company_id=cid,
                label="x",
                ship_value=1,
                prod_value=0,
            )
        )
        db.commit()
    finally:
        db.close()


def test_plan_company_purge_counts_targets():
    _seed_company("keep_co")
    _seed_company("drop_co")
    db = SessionLocal()
    try:
        plan = plan_company_purge(db, ["keep_co"])
        assert plan.keep_ids == ["keep_co"]
        assert "drop_co" in plan.delete_ids
        assert plan.row_counts_by_company["drop_co"]["work_unit"] == 1
    finally:
        db.close()


def test_purge_companies_except_removes_related_rows():
    _seed_company("keep_co")
    _seed_company("drop_co")
    db = SessionLocal()
    try:
        purge_companies_except(db, ["keep_co"])
        assert (
            db.query(models.CompanyMaster)
            .filter(models.CompanyMaster.company_id == "drop_co")
            .first()
            is None
        )
        assert (
            db.query(models.WorkUnit)
            .filter(models.WorkUnit.company_id == "drop_co")
            .count()
            == 0
        )
        assert (
            db.query(models.CompanyMaster)
            .filter(models.CompanyMaster.company_id == "keep_co")
            .count()
            == 1
        )
    finally:
        db.close()


def test_delete_company_and_related_data_is_idempotent_for_missing():
    db = SessionLocal()
    try:
        deleted = delete_company_and_related_data(db, "missing_co")
        db.commit()
        assert deleted["company_master"] == 0
    finally:
        db.close()
