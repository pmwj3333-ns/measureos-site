"""第7条・不足理由（表示レイヤ）の内訳分解。"""

from __future__ import annotations

from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.article7_safety_stock import (
    decompose_shortage_for_display,
    is_manual_priority_item,
    shortage_qty,
)
from app.services.priority_rebuild import rebuild_priority_items_for_company

CO = "a7_reason_test_co"
PASS = "A7ReasonPass1"
NOW = datetime(2026, 5, 19, 10, 0)


def _register_company(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "不足理由テスト"},
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


def test_decompose_pattern_ship_only():
    ship, safety, labels = decompose_shortage_for_display(
        40, 60, 20, safety_stock_unset=True, product_code="P1"
    )
    assert ship == 20.0
    assert safety == 0.0
    assert labels == ["出荷不足"]
    assert ship + safety == 20.0


def test_decompose_pattern_safety_only():
    ship, safety, labels = decompose_shortage_for_display(
        40, 20, 20, safety_stock_unset=False, product_code="P1"
    )
    assert ship == 0.0
    assert safety == 20.0
    assert labels == ["基準在庫不足"]
    assert ship + safety == 20.0


def test_decompose_pattern_both():
    ship, safety, labels = decompose_shortage_for_display(
        40, 80, 70, safety_stock_unset=False, product_code="P1"
    )
    assert ship == 40.0
    assert safety == 30.0
    assert labels == ["出荷不足", "基準在庫不足"]
    assert ship + safety == 70.0


def test_decompose_safety_unset_hides_safety_label():
    """基準在庫未設定（計算0）では基準在庫不足ラベルを出さない。"""
    ship, safety, labels = decompose_shortage_for_display(
        40, 60, 20, safety_stock_unset=True, product_code="P1"
    )
    assert safety == 0.0
    assert "基準在庫不足" not in labels


def test_manual_priority_item_detection():
    assert is_manual_priority_item("")
    assert not is_manual_priority_item("P1")


def test_decompose_manual_entry():
    ship, safety, labels = decompose_shortage_for_display(
        80, 100, 20, safety_stock_unset=True, product_code=""
    )
    assert ship == 20.0
    assert safety == 0.0
    assert labels == ["出荷不足（手入力）"]


def test_shortage_qty_matches_decompose_sum():
    stock, ship, safety_val = 40.0, 80.0, 30
    total = shortage_qty(stock, safety_val, ship)
    ship_part, safety_part, _ = decompose_shortage_for_display(
        stock, ship, total, safety_stock_unset=False, product_code="P1"
    )
    assert total == 70.0
    assert ship_part + safety_part == total


def test_priority_items_api_shortage_reason_rebuild(co_client: TestClient):
    db = SessionLocal()
    try:
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="P1",
                label="商品1",
                is_active=True,
                safety_stock_value=40,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            models.StockItem(
                company_id=CO,
                product_code="P1",
                label="商品1",
                stock_qty=40.0,
                created_at=NOW,
            )
        )
        db.add(
            models.ShipmentPlanItem(
                company_id=CO,
                product_code="P1",
                label="商品1",
                ship_qty=20.0,
                due_date="2099-12-31",
                created_at=NOW,
            )
        )
        db.commit()
        rebuild_priority_items_for_company(CO, db)
    finally:
        db.close()

    r = co_client.get("/v2/priority/items", params={"company_id": CO})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["prod_value"] == 20.0
    assert it["shortage_from_ship_qty"] == 0.0
    assert it["shortage_from_safety_qty"] == 20.0
    assert it["shortage_reason_labels"] == ["基準在庫不足"]


def test_priority_items_api_manual_create(co_client: TestClient):
    r = co_client.post(
        "/v2/priority/create",
        json={
            "company_id": CO,
            "items": [
                {
                    "label": "手入力商品",
                    "ship_value": 100,
                    "prod_value": 25,
                    "due_date": "2099-12-31",
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    it = r.json()["items"][0]
    assert it["prod_value"] == 25.0
    assert it["shortage_from_ship_qty"] == 25.0
    assert it["shortage_from_safety_qty"] == 0.0
    assert it["shortage_reason_labels"] == ["出荷不足（手入力）"]
