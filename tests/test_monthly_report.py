"""月報作成 API・集計。"""

from __future__ import annotations

from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.routers.sr_monthly import _render_print_html

CO = "monthly_report_test_co"
BD = "2026-06-15"
TASK = "task_m"
PROC = "proc_01"
USER = "L1"


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "月報テスト株式会社"},
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
    _register(client)
    return client


def test_monthly_aggregate_empty(co_client: TestClient):
    r = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == CO
    assert body["company_name"] == "月報テスト株式会社"
    assert body["target_month"] == "2026-06"
    assert body["metrics"]["total_work_count"] == 0
    assert body["metrics"]["audit_response_rate"] == 0.0
    assert body["generated_summary"]


def test_monthly_aggregate_counts_work(co_client: TestClient):
    co_client.put(
        f"/v2/company/{CO}/leaders",
        json={
            "leaders": [
                {"name": "L1", "process": "工程1"},
                {"name": "L2", "process": "工程2"},
            ],
            "company_name": "月報テスト株式会社",
        },
    )
    w = _shell(co_client)
    uid = w["id"]
    planned = co_client.post(
        f"/v2/work/{uid}/planned",
        json={"lines": [{"label": "商品A", "value": 10}]},
    )
    assert planned.status_code == 200, planned.text
    assert co_client.post(f"/v2/work/{planned.json()['id']}/start", json={}).status_code == 200

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
                due_date="2026-06-20",
                status="open",
                is_after_cutoff=True,
                created_at=datetime(2026, 6, 10, 12, 0, 0),
            )
        )
        db.commit()
    finally:
        db.close()

    r = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    )
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert m["total_work_count"] >= 1
    assert m["planned_registered_count"] >= 1
    assert m["article7_count"] >= 1
    assert m["after_cutoff_count"] >= 1
    assert any(row["label"] == "工程1" for row in m["by_process"])
    assert not any("proc_" in row["label"] for row in m["by_process"])
    assert sum(row["count"] for row in m["by_process"]) == m["total_work_count"]
    assert sum(row["count"] for row in m["by_leader"]) == m["total_work_count"]
    assert any(row["label"] == "L1" for row in m["by_leader"])

    w2 = _shell(co_client, business_date="2026-06-20")
    co_client.put(
        f"/v2/company/{CO}/leaders",
        json={
            "leaders": [
                {"name": "L1", "process": "工程1"},
                {"name": "L2", "process": "工程2"},
            ],
        },
    )
    assert co_client.post(f"/v2/work/{w2['id']}/start", json={}).status_code == 422
    reg_empty = co_client.post(f"/v2/work/{w2['id']}/planned", json={"lines": []})
    assert reg_empty.status_code == 200, reg_empty.text
    assert co_client.post(f"/v2/work/{reg_empty.json()['id']}/start", json={}).status_code == 200
    r2 = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    )
    body = r2.json()
    assert body["metrics"]["started_without_planned_count"] == 0
    assert "予告なし着手" not in body["generated_summary"]


def test_monthly_save_and_print(co_client: TestClient):
    agg = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-05"},
    )
    assert agg.status_code == 200, agg.text
    summary = agg.json()["generated_summary"]

    saved = co_client.post(
        "/v2/sr/monthly-report",
        json={
            "company_id": CO,
            "target_month": "2026-05",
            "generated_summary": summary,
            "consultant_comment": "経営者向けコメント",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["id"] > 0
    assert body["consultant_comment"] == "経営者向けコメント"

    again = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-05"},
    )
    assert again.json()["consultant_comment"] == "経営者向けコメント"

    pr = co_client.get(
        "/v2/sr/monthly-report/print",
        params={"company_id": CO, "target_month": "2026-05"},
    )
    assert pr.status_code == 200
    m = again.json()["metrics"]
    rate = float(m.get("audit_response_rate") or 0.0)
    assert "MEASURE OS 月報" in pr.text
    assert "月報テスト株式会社" in pr.text
    assert "② 異常発生状況" in pr.text
    assert "③ 監査対応状況" in pr.text
    assert "監査対応率:" in pr.text
    assert "実績入力済み" in pr.text
    assert "実績未入力" in pr.text
    assert "actual_at（実績登録）" in pr.text
    assert f"{rate:g}%" in pr.text


def test_monthly_anomaly_breakdown_in_aggregate(co_client: TestClient):
    _shell(co_client)
    r = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    )
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert "anomaly_breakdown" in m
    assert len(m["anomaly_breakdown"]) == 5
    assert "audit_breakdown" in m
    assert "audit_target_count" in m
    assert "audit_response_rate" in m
    assert m["anomaly_breakdown_note"]


def test_sr_monthly_page_route(client: TestClient):
    r = client.get("/sr/monthly")
    assert r.status_code == 200
    assert "月報作成" in r.text
    assert "/v2/sr/monthly-report/aggregate" in r.text
    assert "anomaly-breakdown-list" in r.text
    assert "audit-breakdown-list" in r.text
    assert "audit-rate-grid" in r.text
    assert "監査対応率" in r.text
    assert "実績入力済み" in r.text
    assert "実績未入力" in r.text
    assert "work-status-note" in r.text
    assert "/static/sr_monthly_url_state.js" in r.text
    assert "monthly_target_month" in r.text


def test_print_html_audit_rate_matches_metrics():
    payload = {
        "company_name": "テスト",
        "target_month_label": "2026年5月",
        "generated_summary": "",
        "consultant_comment": "",
        "metrics": {
            "total_work_count": 25,
            "completed_count": 10,
            "incomplete_count": 15,
            "anomaly_breakdown": [],
            "audit_target_count": 22,
            "audit_response_rate": 22.7,
            "audit_breakdown": [
                {"key": "blue", "label": "未確認", "count": 17},
                {"key": "closed", "label": "確認済み", "count": 5},
                {"key": "red", "label": "期限超過", "count": 0},
            ],
            "audit_breakdown_note": "注記",
        },
    }
    html = _render_print_html(payload)
    assert "監査対応率:" in html
    assert "22.7%" in html
    assert "実績入力済み" in html
    assert "actual_at（実績登録）" in html


def test_monthly_invalid_month(co_client: TestClient):
    r = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-13"},
    )
    assert r.status_code == 422
