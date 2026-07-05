"""Audit Head 選定（監査・観測用代表行）。"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.services.audit_head import (
    audit_heads_from_rows,
    is_completely_empty_shell,
    is_successor_shell,
    select_audit_head_for_nk,
)
from tests.office_latest_aggregate import collect_office_anomaly_rows
from tests.conftest import v2_register_planned

NK = {
    "company_id": "co",
    "task_id": "task_01",
    "process_id": "proc_01",
    "user_id": "二宮",
    "business_date": "2026-06-12",
}


def _row(**kw) -> dict:
    base = {
        **NK,
        "planned_at": None,
        "started_at": None,
        "actual_at": None,
        "status": "blue",
        "is_article7_deviation": False,
        "deviation_reason": None,
        "anomaly_classification": None,
        "pattern_a": None,
        "pattern_b": None,
    }
    base.update(kw)
    return base


def test_empty_shell_not_audit_candidate():
    r = _row(id=575)
    assert is_completely_empty_shell(r) is True
    assert select_audit_head_for_nk([r]) is None


def test_successor_shell_skipped_actual_row_is_head():
    r574 = _row(
        id=574,
        actual_at="2026-06-13T17:10:18",
        is_article7_deviation=True,
        deviation_reason="テスト",
        anomaly_classification={
            "process": ["sequence_skip"],
            "result": ["material_shortage"],
        },
        pattern_a=True,
        pattern_b=True,
    )
    r575 = _row(id=575, status="blue")
    versions = [r574, r575]
    assert is_successor_shell(r575, versions) is True
    head = select_audit_head_for_nk(versions)
    assert head is not None
    assert head["id"] == 574


def test_office_anomaly_uses_audit_head_not_successor_shell():
    r574 = _row(
        id=574,
        actual_at="2026-06-13T17:10:18",
        is_article7_deviation=True,
        deviation_reason="テスト",
    )
    r575 = _row(id=575)
    out = collect_office_anomaly_rows([r574, r575], effective_gt_bd=False)
    assert len(out) == 1
    assert out[0]["id"] == 574


def test_audit_heads_from_rows_multiple_nk():
    a = _row(id=1, company_id="a", actual_at="2026-06-01T00:00:00")
    b = _row(id=2, company_id="b", actual_at="2026-06-01T00:00:00")
    heads = audit_heads_from_rows([a, b])
    assert len(heads) == 2


CO = "audit_head_api_co"
TASK = "task_ah"
PROC = "proc_ah"
USER = "班長:AuditHead"
BD = "2026-06-12"


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "Audit Head API Test"},
    )
    assert r.status_code == 200, r.text
    return client


def test_sr_dashboard_and_monthly_use_audit_head(co_client: TestClient):
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
            "pattern_a": True,
            "pattern_b": True,
            "deviation_reason": "テスト",
            "anomaly_classification": {
                "process": ["sequence_skip"],
                "result": ["material_shortage"],
            },
        },
    )
    shell = co_client.post(
        "/v2/work",
        json={
            "company_id": CO,
            "task_id": TASK,
            "process_id": PROC,
            "user_id": USER,
            "business_date": BD,
        },
    ).json()
    assert shell["id"] > uid
    assert not shell.get("actual_at")

    dash = co_client.get(
        "/v2/sr/observe-dashboard", params={"company_id": CO}
    ).json()
    assert dash["summary"]["blue_count"] >= 1
    assert dash["summary"]["exception_input_count"] >= 1
    fc = dash["field_classification_breakdown"]
    proc = {r["code"]: r["count"] for r in fc.get("process") or []}
    assert proc.get("sequence_skip") == 1

    monthly = co_client.get(
        "/v2/sr/monthly-report/aggregate",
        params={"company_id": CO, "target_month": "2026-06"},
    ).json()
    m = monthly["metrics"]
    assert m["audit_target_count"] >= 1
    assert m["anomaly_count"] >= 1
    mfc = m["field_classification_breakdown"]
    mproc = {r["code"]: r["count"] for r in mfc.get("process") or []}
    assert mproc.get("sequence_skip") == 1
