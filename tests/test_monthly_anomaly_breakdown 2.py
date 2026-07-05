"""月報: 異常発生・監査対応の独立集計。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app import models
from app.database import SessionLocal
from app.routers.work import _get_or_create_settings
from app.services.monthly_report import (
    ANOMALY_BREAKDOWN_SPECS,
    AUDIT_BREAKDOWN_SPECS,
    _audit_response_rate,
    _count_anomaly_breakdown,
    _count_audit_breakdown,
    _count_rows,
    _load_month_work_rows,
    _row_completed,
    _row_incomplete,
    compute_monthly_metrics,
    generate_monthly_summary,
    parse_target_month,
)
from app.services.test_clock import set_reference_utc_naive


def _settings(**kwargs) -> models.CompanySettings:
    base = dict(
        company_id="monthly_test_co",
        day_boundary_time=time(5, 0),
        package_code="A",
    )
    base.update(kwargs)
    return models.CompanySettings(**base)


def _row(**kwargs):
    base = {
        "business_date": "2026-05-10",
        "status": "normal",
        "is_missing": False,
        "is_invalid_flow": False,
        "is_diff_anomaly": False,
        "is_deviation": False,
        "is_article7_deviation": False,
        "is_unregistered_user": False,
        "system_pattern": "",
    }
    base.update(kwargs)
    return base


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    set_reference_utc_naive(None)


def test_anomaly_breakdown_counts_independently():
    settings = _settings()
    set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))
    done = {"actual_at": "2026-05-01T12:00:00", "status": "closed"}
    rows = [
        _row(
            status="normal",
            business_date="2026-06-12",
            actual_at="2026-06-12T10:00:00",
        ),
        _row(is_invalid_flow=True, **done),
        _row(is_diff_anomaly=True, **done),
        _row(is_deviation=True, actual_at="2026-05-02T10:00:00"),
        _row(is_unregistered_user=True, actual_at="2026-05-03T10:00:00"),
        _row(is_invalid_flow=True, is_diff_anomaly=True, **done),
        _row(status="blue", started_at="2026-05-01T09:00:00"),
        _row(
            is_invalid_flow=True,
            started_at="2026-05-01T09:00:00",
            planned_registered_at="2026-05-01T08:00:00",
        ),
    ]
    metrics = _count_rows(rows, settings=settings)
    breakdown = {r["key"]: r["count"] for r in metrics["anomaly_breakdown"]}
    assert breakdown["carryover"] == 2
    assert breakdown["invalid_flow"] == 3
    assert breakdown["diff_anomaly"] == 2
    assert breakdown["deviation"] == 1
    assert breakdown["unregistered_user"] == 1
    assert metrics["incomplete_count"] == 2


def test_closed_row_keeps_invalid_flow_in_breakdown():
    settings = _settings()
    row = _row(is_invalid_flow=True, status="closed", **{"actual_at": "2026-05-01T10:00:00"})
    breakdown = {r["key"]: r["count"] for r in _count_anomaly_breakdown([row], settings)}
    assert breakdown["invalid_flow"] == 1


def test_audit_response_rate_calculation():
    assert _audit_response_rate(5, 22) == 22.7
    assert _audit_response_rate(0, 0) == 0.0
    assert _audit_response_rate(3, 10) == 30.0


def test_audit_breakdown_includes_response_rate():
    settings = _settings()
    rows = [
        {
            "id": 1,
            "company_id": "co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-10",
            "status": "blue",
            "actual_at": "2026-05-01T09:00:00",
            "is_invalid_flow": True,
        },
        {
            "id": 2,
            "company_id": "co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-10",
            "status": "closed",
            "actual_at": "2026-05-01T09:00:00",
            "is_invalid_flow": True,
        },
    ]
    audit = _count_audit_breakdown(rows, settings, suppressed_peer_ids=set())
    assert audit["audit_target_count"] == 1
    assert audit["audit_response_rate"] == 100.0


def test_audit_breakdown_targets_anomaly_occurrence_rows():
    settings = _settings()
    rows = [
        {
            "id": 1,
            "company_id": "co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-10",
            "status": "blue",
            "actual_at": "2026-05-01T09:00:00",
            "is_invalid_flow": True,
        },
        {
            "id": 2,
            "company_id": "co",
            "task_id": "t",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-10",
            "status": "closed",
            "actual_at": "2026-05-01T09:00:00",
            "is_invalid_flow": True,
        },
        {
            "id": 3,
            "company_id": "co",
            "task_id": "t2",
            "process_id": "p",
            "user_id": "u",
            "business_date": "2026-05-11",
            "status": "blue",
            "actual_at": "2026-05-02T10:00:00",
            "is_invalid_flow": True,
        },
    ]
    audit = _count_audit_breakdown(rows, settings, suppressed_peer_ids=set())
    assert audit["audit_target_count"] == 2
    m = {r["key"]: r["count"] for r in audit["audit_breakdown"]}
    assert m["blue"] == 1
    assert m["closed"] == 1
    assert m["red"] == 0


def test_incomplete_definition_uses_actual_at_only():
    assert not _row_incomplete(_row(actual_at="2026-05-01T10:00:00", status="normal"))
    assert _row_incomplete(_row(status="normal"))
    assert _row_completed(_row(actual_at="2026-05-01T10:00:00", status="closed"))


def test_breakdown_labels_fixed_order():
    settings = _settings()
    breakdown = _count_anomaly_breakdown([], settings)
    assert [r["label"] for r in breakdown] == [label for _, label in ANOMALY_BREAKDOWN_SPECS]
    audit = _count_audit_breakdown([], settings, set())
    assert audit["audit_target_count"] == 0
    assert audit["audit_response_rate"] == 0.0
    assert [r["label"] for r in audit["audit_breakdown"]] == [
        label for _, label in AUDIT_BREAKDOWN_SPECS
    ]


def test_summary_lists_completion_anomalies_and_audit():
    metrics = {
        "total_work_count": 25,
        "completed_count": 10,
        "incomplete_count": 15,
        "anomaly_breakdown": [
            {"key": "carryover", "label": "持ち越し", "count": 15},
            {"key": "invalid_flow", "label": "順序不備", "count": 4},
            {"key": "diff_anomaly", "label": "結果不備", "count": 3},
            {"key": "deviation", "label": "第7条例外", "count": 1},
        ],
        "audit_target_count": 22,
        "audit_response_rate": 22.7,
        "audit_breakdown": [
            {"key": "blue", "label": "未確認", "count": 17},
            {"key": "closed", "label": "確認済み", "count": 5},
            {"key": "red", "label": "期限超過", "count": 0},
        ],
    }
    summary = generate_monthly_summary(metrics, target_month_label="2026年5月")
    assert summary.startswith("2026年5月は総作業数25件。実績入力済み10件、実績未入力15件。")
    assert "持ち越し15件" in summary
    assert "異常発生作業22件のうち、確認済み5件（22.7%）、未確認17件" in summary


def test_test7_may_monthly_metrics():
    db = SessionLocal()
    try:
        _, ms, me = parse_target_month("2026-05")
        rows = _load_month_work_rows(db, "test7", ms, me)
        if not rows:
            pytest.skip("test7/2026-05 data not in test database")
        metrics = compute_monthly_metrics(db, "test7", "2026-05")
        occ = {r["key"]: r["count"] for r in metrics["anomaly_breakdown"]}
        audit = {r["key"]: r["count"] for r in metrics["audit_breakdown"]}
        assert metrics["total_work_count"] == 25
        assert metrics["completed_count"] == 10
        assert metrics["incomplete_count"] == 15
        assert occ["carryover"] == 15
        assert occ["invalid_flow"] == 4
        assert occ["diff_anomaly"] == 3
        assert occ["deviation"] == 1
        # 監査 KPI は異常エピソード（actual_at 単位）ベース。merge 22件とは一致しない。
        assert metrics["audit_target_count"] == 8
        assert metrics["audit_response_rate"] == 100.0
        assert audit["blue"] == 0
        assert audit["closed"] == 8
        assert audit["red"] == 0
    finally:
        db.close()
