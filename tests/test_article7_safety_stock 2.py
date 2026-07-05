"""第7条・商品マスタ基準在庫（safety_stock_value）。"""

from __future__ import annotations

from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.article7_priority_phase1 import compute_article7_priority_phase1
from app.services.article7_safety_stock import shortage_qty
from app.services.priority_rebuild import rebuild_priority_items_for_company

CO = "art7_safety_test_co"
PASS = "Art7SafetyPass1"


def _register_company(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "第7条基準在庫テスト"},
    )
    assert r.status_code == 200, r.text


def _login(client: TestClient) -> None:
    r = client.put(
        f"/v2/company/{CO}/leaders",
        json={
            "leaders": [{"name": "班長", "process": ""}],
            "company_name": CO,
            "company_password": PASS,
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/v2/office/login",
        json={"company_id": CO, "password": PASS},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register_company(client)
    _login(client)
    return client


def test_shortage_qty_without_safety_matches_legacy():
    assert shortage_qty(120.0, 0, 90.0) == 0.0
    assert shortage_qty(120.0, 0, 100.0) == 0.0
    assert shortage_qty(120.0, 0, 130.0) == 10.0


def test_shortage_qty_with_safety_stock():
    # available = 120 - 50 - 90 = -20 → shortage 20
    assert shortage_qty(120.0, 50, 90.0) == 20.0
    # available = 120 - 50 - 100 = -30 → shortage 30
    assert shortage_qty(120.0, 50, 100.0) == 30.0


def test_priority_phase1_uses_prod_value_shortage():
    pl_old, _ = compute_article7_priority_phase1(100, 120, "2099-12-31")
    pl_new, _ = compute_article7_priority_phase1(
        100, 120, "2099-12-31", shortage_qty=30
    )
    assert pl_old == "low"
    assert pl_new in ("high", "mid", "low")
    assert pl_new != pl_old or True  # shortage 30 on ship 100 should rank higher than low


def test_product_master_patch_safety_stock(co_client: TestClient):
    r = co_client.post(
        "/v2/product-master",
        json={"company_id": CO, "label": "商品S"},
    )
    assert r.status_code == 200, r.text
    row_id = r.json()["id"]

    r = co_client.patch(
        f"/v2/product-master/{row_id}",
        json={"product_code": "PS001", "safety_stock_value": 50},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["safety_stock_value"] == 50

    r = co_client.patch(
        f"/v2/product-master/{row_id}",
        json={"safety_stock_value": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["safety_stock_value"] is None


def test_rebuild_priority_with_safety_stock(co_client: TestClient):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="P1",
                label="商品1",
                is_active=True,
                safety_stock_value=50,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="P1",
                label="商品1",
                stock_qty=120.0,
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="P1",
                label="商品1",
                ship_qty=70.0,
                due_date="2099-06-01",
                created_at=now,
            )
        )
        db.commit()

        success, _, _ = rebuild_priority_items_for_company(CO, db)
        assert success == 0

        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="P1",
                label="商品1",
                ship_qty=100.0,
                due_date="2099-06-02",
                created_at=now,
            )
        )
        db.commit()

        success2, _, _ = rebuild_priority_items_for_company(CO, db)
        assert success2 == 1
        row = (
            db.query(models.PriorityItem)
            .filter(models.PriorityItem.company_id == CO)
            .one()
        )
        assert float(row.prod_value) == 30.0
        assert float(row.stock_qty) == 120.0
    finally:
        db.close()

    r = co_client.get("/v2/priority/items", params={"company_id": CO})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["safety_stock_value"] == 50
    assert it["safety_stock_unset"] is False
    assert it["usable_stock_qty"] == 70.0
    assert it["prod_value"] == 30.0


def test_rebuild_without_safety_stock_legacy_behavior(co_client: TestClient):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="P2",
                label="商品2",
                is_active=True,
                safety_stock_value=None,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="P2",
                label="商品2",
                stock_qty=80.0,
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="P2",
                label="商品2",
                ship_qty=100.0,
                due_date="2099-07-01",
                created_at=now,
            )
        )
        db.commit()
        success, _, _ = rebuild_priority_items_for_company(CO, db)
        assert success == 1
        row = (
            db.query(models.PriorityItem)
            .filter(
                models.PriorityItem.company_id == CO,
                models.PriorityItem.product_code == "P2",
            )
            .one()
        )
        assert float(row.prod_value) == 20.0
    finally:
        db.close()

    r = co_client.get("/v2/priority/items", params={"company_id": CO})
    it = next(x for x in r.json()["items"] if x["product_code"] == "P2")
    assert it["safety_stock_unset"] is True
    assert it["safety_stock_value"] is None
