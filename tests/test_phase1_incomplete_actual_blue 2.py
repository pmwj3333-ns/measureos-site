"""第5条: 持ち越し青判定（actual_at なし + effective_date > business_date）。"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from app.database import SessionLocal
from app import models
from app.routers.work import (
    _get_or_create_settings,
    _sync_status_blue_from_derived_flags,
)
from app.services.business_date import effective_calendar_date_jst
from app.services.judgement_promote import (
    carryover_implies_status_blue,
    carryover_implies_status_blue_unit,
)
from app.services.monthly_report import _load_month_work_rows, _row_incomplete, parse_target_month
from app.services.package_a_observe import (
    passes_observe_anomaly_display,
    row_carryover_implies_status_blue,
    row_completely_empty_legacy_triplet,
)
from app.services.test_clock import set_reference_utc_naive

TZ = ZoneInfo("Asia/Tokyo")


@pytest.fixture(autouse=True)
def _reset_test_clock():
    yield
    set_reference_utc_naive(None)


def _settings(boundary: time = time(5, 0)) -> models.CompanySettings:
    return models.CompanySettings(
        company_id="carryover_test_co",
        day_boundary_time=boundary,
        package_code="A",
    )


def test_effective_calendar_date_boundary_examples():
    boundary = time(5, 0)
    jst_459 = datetime(2026, 6, 13, 4, 59, tzinfo=TZ)
    jst_501 = datetime(2026, 6, 13, 5, 1, tzinfo=TZ)
    assert effective_calendar_date_jst(jst_459, boundary) == date(2026, 6, 12)
    assert effective_calendar_date_jst(jst_501, boundary) == date(2026, 6, 13)


def test_carryover_user_examples():
    settings = _settings(time(5, 0))
    row_bd = date(2026, 6, 12)

    set_reference_utc_naive(datetime(2026, 6, 12, 19, 59))  # JST 06-13 04:59
    assert not carryover_implies_status_blue(
        actual_at=None, business_date=row_bd, status="normal", settings=settings
    )

    set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))  # JST 06-13 05:01
    assert carryover_implies_status_blue(
        actual_at=None, business_date=row_bd, status="normal", settings=settings
    )


def test_actual_at_blocks_carryover():
    settings = _settings()
    set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))
    assert not carryover_implies_status_blue(
        actual_at=datetime(2026, 6, 12, 14, 50),
        business_date=date(2026, 6, 12),
        status="normal",
        settings=settings,
    )


def test_closed_blocks_carryover():
    settings = _settings()
    set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))
    assert not carryover_implies_status_blue(
        actual_at=None,
        business_date=date(2026, 6, 12),
        status="closed",
        settings=settings,
    )


def test_same_day_not_carryover_blue():
    db = SessionLocal()
    try:
        settings = _get_or_create_settings("carryover_test_co", db)
        settings.day_boundary_time = time(5, 0)
        u = models.WorkUnit(
            company_id="carryover_test_co",
            task_id="t1",
            process_id="p1",
            user_id="u1",
            business_date=date(2026, 6, 12),
            status="normal",
            planned_registered_at=datetime(2026, 6, 12, 8, 0),
            planned_value=10.0,
            started_at=datetime(2026, 6, 12, 9, 0),
        )
        set_reference_utc_naive(datetime(2026, 6, 12, 14, 50))  # JST 23:50 same effective day
        assert not carryover_implies_status_blue_unit(u, settings)
        _sync_status_blue_from_derived_flags(u, db)
        assert u.status == "normal"
    finally:
        db.close()


def test_empty_triplet_past_date_is_carryover_blue():
    settings = _settings()
    set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))
    row = {
        "status": "blue",
        "business_date": "2026-06-10",
        "planned_registered_at": None,
        "planned_value": None,
        "started_at": None,
        "actual_at": None,
        "actual_value": None,
    }
    assert row_completely_empty_legacy_triplet(row)
    assert row_carryover_implies_status_blue(row, settings)
    assert passes_observe_anomaly_display(row, settings)


def test_sync_status_blue_carryover():
    db = SessionLocal()
    try:
        settings = _get_or_create_settings("carryover_test_co", db)
        settings.day_boundary_time = time(5, 0)
        db.commit()
        u = models.WorkUnit(
            company_id="carryover_test_co",
            task_id="t1",
            process_id="p1",
            user_id="u1",
            business_date=date(2026, 6, 10),
            status="normal",
            started_at=datetime(2026, 6, 10, 9, 0),
        )
        set_reference_utc_naive(datetime(2026, 6, 12, 20, 1))
        _sync_status_blue_from_derived_flags(u, db)
        assert u.status == "blue"
    finally:
        db.close()


def test_test7_may_carryover_blue_counts():
    """ローカル measure_os.db に test7/2026-05 がある環境でのみ検証。"""
    db = SessionLocal()
    try:
        settings = _get_or_create_settings("test7", db)
        _, ms, me = parse_target_month("2026-05")
        rows = _load_month_work_rows(db, "test7", ms, me)
        inc = [r for r in rows if _row_incomplete(r)]
        if not inc:
            pytest.skip("test7/2026-05 data not in test database")
        blue_inc = [
            r
            for r in inc
            if (r.get("status") or "").lower() == "blue"
            and passes_observe_anomaly_display(r, settings)
        ]
        empty = sum(1 for r in inc if row_completely_empty_legacy_triplet(r))
        closed = sum(1 for r in inc if (r.get("status") or "").lower() == "closed")
        assert len(inc) == 15
        assert empty == 11
        assert closed == 1
        assert len(blue_inc) == 14
    finally:
        db.close()
