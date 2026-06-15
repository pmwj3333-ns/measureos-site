"""office_v2「要注意（青・赤）」: natural key 最新1行への集約。"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import func

from app import models
from app.database import SessionLocal
from app.routers.work import _get_or_create_settings, _unit_to_out, promote_blue_to_red_after_judgement
from app.services.package_a_observe import passes_observe_anomaly_display
from tests.office_latest_aggregate import collect_office_anomaly_rows

logging.disable(logging.CRITICAL)


def _row(
    *,
    id: int,
    business_date: str = "2026-05-05",
    status: str = "blue",
    actual_at: str | None = None,
    started_at: str | None = "2026-05-05T08:00:00",
    planned_at: str | None = None,
    is_invalid_flow: bool = False,
    is_article7_deviation: bool = False,
) -> dict:
    return {
        "id": id,
        "company_id": "co",
        "task_id": "task_01",
        "process_id": "proc_01",
        "user_id": "a",
        "business_date": business_date,
        "status": status,
        "actual_at": actual_at,
        "planned_at": planned_at,
        "started_at": started_at,
        "is_invalid_flow": is_invalid_flow,
        "is_diff_anomaly": False,
        "is_missing": False,
        "is_article7_deviation": is_article7_deviation,
        "system_pattern": "",
    }


def test_collect_office_anomaly_keeps_latest_id_per_natural_key():
    rows = [
        _row(id=1, status="blue"),
        _row(id=2, status="blue", is_invalid_flow=True),
    ]
    out = collect_office_anomaly_rows(rows, effective_gt_bd=False)
    assert len(out) == 1
    assert out[0]["id"] == 2


def test_collect_office_anomaly_prefers_audit_head_over_successor_shell():
    rows = [
        _row(
            id=574,
            status="blue",
            actual_at="2026-06-13T17:10:18",
            is_article7_deviation=True,
        ),
        _row(id=575, status="blue", started_at=None, planned_at=None, actual_at=None),
    ]
    out = collect_office_anomaly_rows(rows, effective_gt_bd=False)
    assert len(out) == 1
    assert out[0]["id"] == 574


def test_collect_office_anomaly_collapses_blue_history_to_latest():
    rows = [
        _row(id=1, status="blue", is_invalid_flow=True),
        _row(id=2, status="blue", is_invalid_flow=True),
        _row(id=3, status="blue", is_invalid_flow=True),
    ]
    out = collect_office_anomaly_rows(rows, effective_gt_bd=False)
    assert len(out) == 1
    assert out[0]["id"] == 3


def test_collect_office_anomaly_drops_history_when_latest_is_normal():
    rows = [
        _row(id=10, status="blue", is_invalid_flow=True),
        _row(id=11, status="blue", is_invalid_flow=True),
        _row(id=12, status="normal", started_at=None, planned_at=None, actual_at=None),
    ]
    out = collect_office_anomaly_rows(rows, effective_gt_bd=False)
    assert len(out) == 1
    assert out[0]["id"] == 11


def test_collect_office_anomaly_excludes_closed_latest():
    rows = [
        _row(id=20, status="blue"),
        _row(id=21, status="closed", started_at=None),
    ]
    out = collect_office_anomaly_rows(rows, effective_gt_bd=False)
    assert out == []


def test_office_v2_html_uses_audit_head_for_attention():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "frontend" / "office_v2.html").read_text(
        encoding="utf-8"
    )
    assert "function auditHeadsFromRows" in html
    assert "function latestRowsByNaturalKey" in html
    fn = html[html.index("function collectOfficeAnomalySortedRows") : html.index(
        "function collectLatestActualRows"
    )]
    assert "auditHeadsFromRows(sourceRows)" in fn


def test_test7_office_anomaly_count_after_dedup():
    db = SessionLocal()
    try:
        cid = "test7"
        settings = _get_or_create_settings(cid, db)
        promote_blue_to_red_after_judgement(cid, db)
        db.commit()
        suppressed_sq = db.query(models.OfficeClosedWorkUnitSuppress.peer_unit_id)
        sort_key = func.coalesce(models.WorkUnit.updated_at, models.WorkUnit.created_at)
        units = (
            db.query(models.WorkUnit)
            .filter(models.WorkUnit.company_id == cid)
            .filter(~models.WorkUnit.id.in_(suppressed_sq))
            .order_by(sort_key.desc().nulls_last(), models.WorkUnit.id.desc())
            .limit(200)
            .all()
        )
        if not units:
            pytest.skip("test7 data not in test database")
        rows = [_unit_to_out(u, settings, db, None, office_chain_hint="") for u in units]

        before = [
            r
            for r in rows
            if (r.get("status") or "").lower() in ("blue", "red")
            and (r.get("status") or "").lower() != "closed"
            and (
                (r.get("status") or "").lower() == "red"
                or passes_observe_anomaly_display(r, settings)
            )
        ]
        after = [
            r
            for r in collect_office_anomaly_rows(rows, effective_gt_bd=True)
            if passes_observe_anomaly_display(r, settings)
            or (r.get("status") or "").lower() == "red"
        ]
        assert len(before) > len(after)
        assert len(after) == 21
        assert len(after) < 30
    finally:
        db.close()
