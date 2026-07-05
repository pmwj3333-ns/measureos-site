"""現場分類の表示補完（system → A/B、DB 変更なし）。"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.services.anomaly_classification import (
    aggregate_field_classification,
    infer_auto_process_display,
    infer_auto_result_display,
    is_article7_only_without_ab,
    resolve_field_classification_display,
    row_has_field_classification_input,
)

NK = {
    "company_id": "co",
    "task_id": "t",
    "process_id": "p",
    "user_id": "u",
    "business_date": "2026-06-12",
}


def _row(**kw) -> dict:
    base = {
        **NK,
        "planned_at": None,
        "started_at": None,
        "actual_at": None,
        "planned_registered_at": None,
        "pattern_a": None,
        "pattern_b": None,
        "anomaly_classification": None,
        "system_pattern": "",
        "is_invalid_flow": False,
        "is_diff_anomaly": False,
        "is_article7_deviation": False,
        "is_deviation": False,
        "is_missing": False,
    }
    base.update(kw)
    return base


def test_field_input_takes_priority():
    row = _row(
        pattern_a=True,
        anomaly_classification={"process": ["handoff_missing"], "result": []},
        is_invalid_flow=True,
    )
    assert row_has_field_classification_input(row) is True
    disp = resolve_field_classification_display(row)
    assert disp["mode"] == "field"
    assert disp["section_label"] == "現場分類"


def test_auto_process_no_planned_actual():
    row = _row(
        actual_at="2026-06-13T10:00:00",
        system_pattern="A*",
        is_invalid_flow=True,
    )
    disp = resolve_field_classification_display(row)
    assert disp["mode"] == "auto"
    assert disp["section_label"] == "現場分類（自動判定）"
    assert disp["auto_process"] is True


def test_auto_result_diff_anomaly():
    row = _row(
        actual_at="2026-06-13T10:00:00",
        started_at="2026-06-13T09:00:00",
        planned_registered_at="2026-06-13T08:00:00",
        is_diff_anomaly=True,
        system_pattern="B*",
    )
    disp = resolve_field_classification_display(row)
    assert disp["mode"] == "auto"
    assert disp["auto_result"] is True


def test_empty_actual_report_is_b_not_a():
    """予告（空）→ 着手 → 実績内容なし は B 結果不備。"""
    row = _row(
        planned_registered_at="2026-06-13T08:00:00",
        started_at="2026-06-13T09:00:00",
        actual_at="2026-06-13T10:00:00",
        actual_lines=[],
        is_diff_anomaly=True,
        is_invalid_flow=False,
        system_pattern="B*",
    )
    assert infer_auto_process_display(row) is False
    assert infer_auto_result_display(row) is True
    disp = resolve_field_classification_display(row)
    assert disp["mode"] == "auto"
    assert disp["auto_process"] is False
    assert disp["auto_result"] is True
    out = aggregate_field_classification([row])
    assert out.get("auto_result", {}).get("count") == 1
    assert "auto_process" not in out


def test_article7_only_no_field_classification():
    row = _row(
        is_article7_deviation=True,
        system_pattern="7条逸脱",
        deviation_reason="テスト",
    )
    assert is_article7_only_without_ab(row) is True
    disp = resolve_field_classification_display(row)
    assert disp["mode"] == "none"


def test_aggregate_counts_auto_when_field_empty():
    rows = [
        _row(
            actual_at="2026-06-13T10:00:00",
            is_invalid_flow=True,
            system_pattern="A*",
        ),
        _row(
            actual_at="2026-06-14T10:00:00",
            started_at="2026-06-14T09:00:00",
            planned_registered_at="2026-06-14T08:00:00",
            is_diff_anomaly=True,
        ),
        _row(
            pattern_a=True,
            anomaly_classification={"process": ["handoff_missing"], "result": []},
            actual_at="2026-06-15T10:00:00",
        ),
        _row(is_article7_deviation=True, system_pattern="7条逸脱"),
    ]
    out = aggregate_field_classification(rows)
    assert out["display_mode"] == "mixed"
    assert out["auto_process"]["count"] == 1
    assert out["auto_result"]["count"] == 1
    proc = {r["code"]: r["count"] for r in out["process"]}
    assert proc["handoff_missing"] == 1


from tests.conftest import v2_register_planned

CO = "fc_display_co"
TASK = "task_fc_d"
PROC = "proc_fc_d"
USER = "班長:表示補完"
BD = "2026-06-12"


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "表示補完テスト"},
    )
    assert r.status_code == 200, r.text
    return client


def test_api_auto_display_without_field_input(co_client: TestClient):
    w = co_client.post(
        "/v2/work",
        json={
            "company_id": CO,
            "task_id": TASK,
            "process_id": PROC,
            "user_id": USER,
            "business_date": BD,
        },
    ).json()
    uid = w["id"]
    reg = v2_register_planned(co_client, uid, lines=[])
    started = co_client.post(f"/v2/work/{reg['id']}/start", json={}).json()
    co_client.post(
        f"/v2/work/{started['id']}/actual",
        json={
            "lines": [{"label": "商品A", "value": 1}],
            "pattern_a": False,
            "pattern_b": False,
        },
    )

    dash = co_client.get(
        "/v2/sr/observe-dashboard", params={"company_id": CO}
    ).json()
    fc = dash["field_classification_breakdown"]
    assert fc.get("auto_process") or fc.get("process")

    monthly = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    ).json()
    m = monthly["metrics"]
    # A* 自動表示のみでは actual_at 付き異常エピソードにならない（監査対象 0 は正）
    assert m["field_classification_breakdown"]
