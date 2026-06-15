"""現場分類（参考）集計 — 社労士ダッシュボード・月報。"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.routers.sr_monthly import _render_print_html
from app.services.anomaly_classification import aggregate_field_classification

CO = "field_fc_test_co"
TASK = "task_fc"
PROC = "proc_fc"
USER = "班長:現場分類"
BD = "2026-05-12"


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "現場分類集計テスト"},
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


def _actual(client: TestClient, uid: int, classification: dict) -> None:
    process = classification.get("process") or []
    result = classification.get("result") or []
    r = client.post(
        f"/v2/work/{uid}/actual",
        json={
            "deviation_reason": "7条逸脱（テスト）",
            "lines": [{"label": "商品A", "value": 1}],
            "pattern_a": bool(process),
            "pattern_b": bool(result),
            "anomaly_classification": classification,
        },
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register(client)
    return client


def test_aggregate_field_classification_counts_subs_only():
    rows = [
        {
            "anomaly_classification": {
                "process": ["handoff_missing", "deferred"],
                "result": ["material_shortage"],
            }
        },
        {
            "anomaly_classification": {
                "process": ["handoff_missing"],
                "result": [],
            }
        },
        {"anomaly_classification": {"process": [], "result": []}},
        {"anomaly_classification": None},
    ]
    out = aggregate_field_classification(rows)
    assert out["note"]
    proc = {r["code"]: r["count"] for r in out["process"]}
    result = {r["code"]: r["count"] for r in out["result"]}
    assert proc["handoff_missing"] == 2
    assert proc["deferred"] == 1
    assert result["material_shortage"] == 1
    assert "input_forgotten" not in proc


def test_observe_dashboard_includes_field_classification(co_client: TestClient):
    w1 = _shell(co_client, "2026-05-10")
    w2 = _shell(co_client, "2026-05-11")
    _actual(
        co_client,
        w1["id"],
        {
            "process": ["input_forgotten", "handoff_missing"],
            "result": ["material_shortage"],
        },
    )
    _actual(
        co_client,
        w2["id"],
        {
            "process": ["handoff_missing"],
            "result": ["material_shortage", "work_error"],
        },
    )

    r = co_client.get("/v2/sr/observe-dashboard", params={"company_id": CO})
    assert r.status_code == 200, r.text
    fc = r.json()["field_classification_breakdown"]
    proc = {row["code"]: row["count"] for row in fc["process"]}
    result = {row["code"]: row["count"] for row in fc["result"]}
    assert proc["input_forgotten"] == 1
    assert proc["handoff_missing"] == 2
    assert result["material_shortage"] == 2
    assert result["work_error"] == 1


def test_monthly_aggregate_includes_field_classification(co_client: TestClient):
    w = _shell(co_client, "2026-06-03")
    _actual(
        co_client,
        w["id"],
        {
            "process": ["deferred"],
            "result": ["equipment_stop"],
        },
    )

    r = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    )
    assert r.status_code == 200, r.text
    fc = r.json()["metrics"]["field_classification_breakdown"]
    proc = {row["code"]: row["count"] for row in fc["process"]}
    result = {row["code"]: row["count"] for row in fc["result"]}
    assert proc["deferred"] == 1
    assert result["equipment_stop"] == 1


def test_monthly_pdf_html_includes_field_classification_section():
    html = _render_print_html(
        {
            "company_name": "テスト",
            "target_month_label": "2026年6月",
            "generated_summary": "サマリー",
            "consultant_comment": "",
            "metrics": {
                "total_work_count": 1,
                "completed_count": 1,
                "incomplete_count": 0,
                "anomaly_breakdown": [],
                "audit_target_count": 0,
                "audit_response_rate": 0.0,
                "audit_breakdown": [],
                "field_classification_breakdown": {
                    "note": "※Package Aでは任意入力のため参考値です。※未入力は異常なしを意味しません。",
                    "process": [{"code": "deferred", "label": "後回し", "count": 2}],
                    "result": [{"code": "material_shortage", "label": "材料不足", "count": 1}],
                },
            },
        }
    )
    assert "②-b 現場分類（任意入力）" in html
    assert "後回し" in html
    assert "材料不足" in html


def test_sr_v2_html_has_field_classification_section():
    text = open("frontend/sr_v2.html", encoding="utf-8").read()
    assert "現場分類（任意入力）" in text
    assert "observe-field-classification-process" in text


def test_sr_monthly_html_has_field_classification_section():
    text = open("frontend/sr_monthly.html", encoding="utf-8").read()
    assert "②-b 現場分類（任意入力）" in text
    assert "field-classification-process" in text
