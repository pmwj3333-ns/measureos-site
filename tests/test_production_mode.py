"""第7条・product_master.production_mode（製造区分）。"""

from __future__ import annotations

from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.production_mode import (
    PRODUCTION_MODE_MANUFACTURE,
    PRODUCTION_MODE_PURCHASE,
    load_production_mode_maps,
    normalize_production_mode,
    resolve_production_mode,
)
from app.services.priority_rebuild import rebuild_priority_items_for_company

CO = "prod_mode_test_co"


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "製造区分テスト"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register(client)
    return client


def test_normalize_production_mode_defaults():
    assert normalize_production_mode(None) == PRODUCTION_MODE_MANUFACTURE
    assert normalize_production_mode("purchase") == PRODUCTION_MODE_PURCHASE
    assert normalize_production_mode("invalid") == PRODUCTION_MODE_MANUFACTURE


def test_product_master_patch_production_mode(co_client: TestClient):
    r = co_client.post(
        "/v2/product-master",
        json={"company_id": CO, "label": "商社品X"},
    )
    assert r.status_code == 200, r.text
    row_id = r.json()["id"]
    assert r.json()["production_mode"] == "manufacture"

    r2 = co_client.patch(
        f"/v2/product-master/{row_id}",
        json={"production_mode": "purchase"},
    )
    assert r2.status_code == 200, r.text
    assert r2.json()["production_mode"] == "purchase"


def test_priority_items_include_production_mode(co_client: TestClient):
    db = SessionLocal()
    try:
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="自社A",
                product_code="M1",
                is_active=True,
                production_mode="manufacture",
            )
        )
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="商社B",
                product_code="P1",
                is_active=True,
                production_mode="purchase",
            )
        )
        now = datetime.utcnow()
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="M1",
                label="自社A",
                stock_qty=1.0,
                created_at=now,
            )
        )
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="P1",
                label="商社B",
                stock_qty=1.0,
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="M1",
                label="自社A",
                ship_qty=10.0,
                due_date="2026-06-01",
                created_at=now,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="P1",
                label="商社B",
                ship_qty=20.0,
                due_date="2026-06-01",
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        rebuild_priority_items_for_company(CO, db2)
    finally:
        db2.close()

    r = co_client.get("/v2/priority/items", params={"company_id": CO})
    assert r.status_code == 200, r.text
    by_label = {it["label"]: it["production_mode"] for it in r.json()["items"]}
    assert by_label.get("自社A") == "manufacture"
    assert by_label.get("商社B") == "purchase"


def test_resolve_production_mode_by_code_and_label():
    db = SessionLocal()
    try:
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="L1",
                product_code="C1",
                production_mode="purchase",
            )
        )
        db.commit()
        by_code, by_label = load_production_mode_maps(db, CO)
        assert resolve_production_mode("C1", "L1", by_code, by_label) == "purchase"
        assert resolve_production_mode("", "L1", by_code, by_label) == "purchase"
        assert resolve_production_mode("UNKNOWN", "UNKNOWN", by_code, by_label) == "manufacture"
    finally:
        db.close()


def test_observe_dashboard_production_mode_counts(co_client: TestClient):
    db = SessionLocal()
    try:
        db.add(
            models.PriorityItem(
                company_id=CO,
                product_code="M1",
                label="自社",
                ship_value=5.0,
                stock_qty=0.0,
                prod_value=5.0,
                status="open",
            )
        )
        db.add(
            models.PriorityItem(
                company_id=CO,
                product_code="P1",
                label="商社",
                ship_value=8.0,
                stock_qty=0.0,
                prod_value=8.0,
                status="open",
            )
        )
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="自社",
                product_code="M1",
                production_mode="manufacture",
            )
        )
        db.add(
            models.ProductMaster(
                company_id=CO,
                label="商社",
                product_code="P1",
                production_mode="purchase",
            )
        )
        db.commit()
    finally:
        db.close()

    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    ps = r.json()["priority_status"]
    assert ps["manufacture_shortage_count"] == 1
    assert ps["purchase_shortage_count"] == 1
    assert ps["shortage_count"] == 2
