"""Package A: 管理者観測ダッシュボード API。"""

from __future__ import annotations

from datetime import datetime, time

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from tests.conftest import v2_register_planned

CO = "sr_observe_test_co"
TASK = "task_ob"
PROC = "組立"
USER = "観測班長:組立"
BD = "2026-05-01"
PREV_BD = "2026-04-30"


def _register_company(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "Package A 観測テスト"},
    )
    assert r.status_code == 200, r.text


def _shell(client: TestClient, business_date: str = BD) -> dict:
    r = client.post(
        "/v2/work",
        json={
            "company_id": CO,
            "task_id": TASK,
            "process_id": PROC,
            "user_id": USER,
            "business_date": business_date,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register_company(client)
    return client


def test_observe_dashboard_empty_company(co_client: TestClient):
    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == CO
    assert body["summary"]["blue_count"] == 0
    assert body["recent_anomalies"] == []
    assert body["priority_status"]["open_item_count"] == 0


def test_observe_dashboard_counts_planned_unstarted_and_priority(co_client: TestClient):
    w = _shell(co_client)
    uid = w["id"]
    r = co_client.post(
        f"/v2/work/{uid}/planned",
        json={
            "lines": [{"label": "商品A", "value": 10}],
            "register": True,
        },
    )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        db.add(
            models.PriorityItem(
                company_id=CO,
                product_code="P1",
                label="商品P1",
                ship_value=5.0,
                stock_qty=2.0,
                prod_value=8.0,
                value=5.0,
                due_date="2026-05-05",
                status="open",
                is_after_cutoff=True,
                created_at=datetime.utcnow(),
            )
        )
        db.add(
            models.ProductMaster(
                company_id=CO,
                product_code="P1",
                label="商品P1",
                is_active=True,
                safety_stock_value=None,
            )
        )
        db.commit()
    finally:
        db.close()

    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["planned_unstarted_count"] >= 1
    assert body["summary"]["blue_count"] >= 1
    assert body["priority_status"]["after_cutoff_count"] >= 1
    assert body["priority_status"]["shortage_count"] >= 1
    assert body["priority_status"]["safety_unset_count"] >= 1
    kinds = {row["kind"] for row in body["recent_anomalies"]}
    assert "未着手予告" in kinds


def test_observe_dashboard_carryover_blue(co_client: TestClient):
    """過去 business_date・actual_at なし → 持ち越し blue_count。"""
    w = _shell(co_client, business_date=PREV_BD)
    uid = w["id"]
    reg = v2_register_planned(co_client, uid, lines=[])
    r = co_client.post(f"/v2/work/{reg['id']}/start", json={})
    assert r.status_code == 200, r.text

    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["blue_count"] >= 1


def test_observe_dashboard_prev_day_incomplete(co_client: TestClient):
    w = _shell(co_client, business_date=PREV_BD)
    uid = w["id"]
    reg = v2_register_planned(co_client, uid, lines=[])
    r = co_client.post(f"/v2/work/{reg['id']}/start", json={})
    assert r.status_code == 200, r.text

    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["prev_day_incomplete_count"] >= 1


def test_observe_dashboard_rejects_empty_company_id(co_client: TestClient):
    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": "  "})
    assert r.status_code == 422
