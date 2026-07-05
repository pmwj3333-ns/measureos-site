"""第3条 Package A: 締切後投入の観測（is_after_cutoff）。"""

from __future__ import annotations

from datetime import datetime, time

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.article3_cutoff_observe import is_after_order_cutoff
from app.services.priority_rebuild import rebuild_priority_items_for_company

CO = "art3_cutoff_test_co"


def _register_company(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "第3条締切テスト"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register_company(client)
    return client


def test_is_after_order_cutoff_unset_cutoff_is_false():
    utc_noon = datetime(2026, 5, 19, 3, 0, 0)  # 12:00 JST
    assert is_after_order_cutoff(utc_noon, None) is False


def test_is_after_order_cutoff_before_and_after():
    before = datetime(2026, 5, 19, 5, 30, 0)  # 14:30 JST
    assert is_after_order_cutoff(before, time(15, 0)) is False
    after = datetime(2026, 5, 19, 6, 30, 0)  # 15:30 JST
    assert is_after_order_cutoff(after, time(15, 0)) is True


def test_rebuild_sets_is_after_cutoff_when_past_cutoff(co_client: TestClient, monkeypatch):
    db = SessionLocal()
    try:
        settings = models.CompanySettings(company_id=CO, order_cutoff_time=time(0, 0))
        db.merge(settings)
        now = datetime(2026, 5, 19, 6, 0, 0)  # 15:00 JST
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="C1",
                label="商品C",
                stock_qty=10.0,
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="C1",
                label="商品C",
                ship_qty=50.0,
                due_date="2099-08-01",
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    import app.services.priority_rebuild as prb

    monkeypatch.setattr(prb, "datetime", type("DT", (), {"utcnow": staticmethod(lambda: now)}))

    db2 = SessionLocal()
    try:
        rebuild_priority_items_for_company(CO, db2)
        row = (
            db2.query(models.PriorityItem)
            .filter(models.PriorityItem.company_id == CO)
            .one()
        )
        assert row.is_after_cutoff is True
    finally:
        db2.close()

    r = co_client.get("/v2/priority/items", params={"company_id": CO})
    assert r.status_code == 200
    assert r.json()["items"][0]["is_after_cutoff"] is True


def test_rebuild_before_cutoff_not_flagged(co_client: TestClient, monkeypatch):
    db = SessionLocal()
    try:
        settings = models.CompanySettings(company_id=CO, order_cutoff_time=time(23, 59))
        db.merge(settings)
        now = datetime(2026, 5, 19, 1, 0, 0)  # 10:00 JST
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="C2",
                label="商品D",
                stock_qty=0.0,
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="C2",
                label="商品D",
                ship_qty=10.0,
                due_date="2099-09-01",
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    import app.services.priority_rebuild as prb

    monkeypatch.setattr(prb, "datetime", type("DT", (), {"utcnow": staticmethod(lambda: now)}))

    db2 = SessionLocal()
    try:
        rebuild_priority_items_for_company(CO, db2)
        row = (
            db2.query(models.PriorityItem)
            .filter(
                models.PriorityItem.company_id == CO,
                models.PriorityItem.product_code == "C2",
            )
            .one()
        )
        assert row.is_after_cutoff is False
    finally:
        db2.close()
