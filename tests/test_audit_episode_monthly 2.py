"""月報監査 KPI: Audit Head / 異常エピソードベース。"""

from __future__ import annotations

import logging

import pytest

from app.services.monthly_report import (
    _count_audit_breakdown,
    _merge_month_versions,
    generate_monthly_summary,
)
from app.services.audit_head import audit_episode_heads_from_rows
from tests.test_monthly_anomaly_breakdown import _settings

logging.disable(logging.CRITICAL)

CO = "co"
TASK = "task_01"
PROC = "proc_01"
USER = "u"
BD = "2026-06-12"


def _nk_row(**kwargs):
    base = {
        "id": 1,
        "company_id": CO,
        "task_id": TASK,
        "process_id": PROC,
        "user_id": USER,
        "business_date": BD,
        "status": "blue",
        "actual_at": None,
        "started_at": None,
        "planned_at": None,
        "is_invalid_flow": False,
        "is_diff_anomaly": False,
        "is_missing": False,
        "is_deviation": False,
        "is_article7_deviation": False,
        "is_unregistered_user": False,
        "system_pattern": "",
    }
    base.update(kwargs)
    return base


def test_episode_excludes_successor_shell_575():
    settings = _settings()
    rows = [
        _nk_row(
            id=574,
            actual_at="2026-06-13T17:10:18",
            is_article7_deviation=True,
        ),
        _nk_row(id=575, status="blue"),
    ]
    has_occ = lambda r: r.get("is_article7_deviation") is True
    episodes = audit_episode_heads_from_rows(rows, has_anomaly_occurrence=has_occ)
    assert len(episodes) == 1
    assert episodes[0]["id"] == 574


def test_case1_closed_574_episode_rate_100():
    """574 確認済み（576 closed + suppress 574）→ 100%。"""
    settings = _settings()
    rows = [
        _nk_row(id=574, actual_at="2026-06-13T17:10:18", is_article7_deviation=True),
        _nk_row(id=575, status="blue"),
        _nk_row(
            id=576,
            status="closed",
            actual_at="2026-06-13T17:10:18",
            is_article7_deviation=True,
        ),
        _nk_row(id=577, status="blue"),
    ]
    audit = _count_audit_breakdown(rows, settings, suppressed_peer_ids={574})
    assert audit["audit_target_count"] == 1
    assert audit["audit_response_rate"] == 100.0
    m = {r["key"]: r["count"] for r in audit["audit_breakdown"]}
    assert m["closed"] == 1
    assert m["blue"] == 0


def test_case2_two_episodes_50_percent():
    """574 確認済み + 580 新規未確認 → 50%。"""
    settings = _settings()
    rows = [
        _nk_row(id=574, actual_at="2026-06-13T17:10:18", is_article7_deviation=True),
        _nk_row(id=576, status="closed", actual_at="2026-06-13T17:10:18", is_article7_deviation=True),
        _nk_row(id=580, actual_at="2026-06-13T18:48:27", is_diff_anomaly=True),
        _nk_row(id=581, status="blue"),
    ]
    audit = _count_audit_breakdown(rows, settings, suppressed_peer_ids={574})
    assert audit["audit_target_count"] == 2
    assert audit["audit_response_rate"] == 50.0
    m = {r["key"]: r["count"] for r in audit["audit_breakdown"]}
    assert m["closed"] == 1
    assert m["blue"] == 1


def test_merge_still_shows_unconfirmed_but_episode_audit_differs():
    """merge 代表 575/581 型でも、エピソード監査は 574 を正しく確認済みにする。"""
    settings = _settings()
    rows = [
        _nk_row(id=574, actual_at="2026-06-13T17:10:18", is_article7_deviation=True),
        _nk_row(id=575, status="blue"),
        _nk_row(id=576, status="closed", actual_at="2026-06-13T17:10:18", is_article7_deviation=True),
    ]
    merged = _merge_month_versions(rows)
    assert merged[0]["id"] == 576
    old_style_would_use_merged_status = merged[0]["status"]
    assert old_style_would_use_merged_status == "closed"

    rows_with_later_shell = rows + [_nk_row(id=581, status="blue")]
    merged2 = _merge_month_versions(rows_with_later_shell)
    assert merged2[0]["id"] == 581
    assert merged2[0]["status"] == "blue"

    audit = _count_audit_breakdown(rows_with_later_shell, settings, {574})
    assert audit["audit_target_count"] == 1
    assert audit["audit_response_rate"] == 100.0


@pytest.mark.integration
def test_co_gidr_june_2026_live_db():
    """measure_os.db の co-gidr 実データ（574 確認済み + 580 未確認）。"""
    from app.database import SessionLocal
    from app.models import CompanyMaster
    from app.services.monthly_report import build_monthly_report_aggregate

    db = SessionLocal()
    try:
        if (
            db.query(CompanyMaster)
            .filter(CompanyMaster.company_id == "co-gidr")
            .first()
            is None
        ):
            pytest.skip("co-gidr not registered in test database")
        rep = build_monthly_report_aggregate(db, "co-gidr", "2026-06")
    finally:
        db.close()
    m = rep["metrics"]
    assert m["audit_target_count"] == 2
    assert m["audit_response_rate"] == 50.0
    audit = {r["key"]: r["count"] for r in m["audit_breakdown"]}
    assert audit["closed"] == 1
    assert audit["blue"] == 1
    assert "確認済み1件（50%）、未確認1件" in rep["generated_summary"]
