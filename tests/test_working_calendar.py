"""Package A: 営業日設定（working_calendar + default_working_weekdays）。"""

from __future__ import annotations

from datetime import date

import pytest
from starlette.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.services.business_date import nearest_workday, next_business_day
from app.services.working_calendar import is_working_day, parse_default_weekdays

CO = "working_cal_test_co"


def _register(client: TestClient) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": CO, "company_name": "営業日テスト"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def co_client(client: TestClient) -> TestClient:
    _register(client)
    return client


def test_parse_default_weekdays_fallback():
    assert parse_default_weekdays(None) == [1, 2, 3, 4, 5]
    assert parse_default_weekdays("[1,2,3,4,5,6]") == [1, 2, 3, 4, 5, 6]


def test_is_working_day_weekday_and_exception(co_client: TestClient):
    db = SessionLocal()
    try:
        settings = models.CompanySettings(
            company_id=CO,
            default_working_weekdays='[1,2,3,4,5]',
        )
        db.merge(settings)
        db.add(
            models.WorkingCalendar(
                company_id=CO,
                target_date=date(2026, 5, 3),
                is_working_day=False,
            )
        )
        db.add(
            models.WorkingCalendar(
                company_id=CO,
                target_date=date(2026, 5, 6),
                is_working_day=True,
            )
        )
        db.commit()

        assert is_working_day(CO, date(2026, 5, 1), db) is True  # Fri
        assert is_working_day(CO, date(2026, 5, 2), db) is False  # Sat
        assert is_working_day(CO, date(2026, 5, 3), db) is False  # Sun exception
        assert is_working_day(CO, date(2026, 5, 6), db) is True  # Wed exception 営業
    finally:
        db.close()


def test_nearest_workday_skips_weekend(co_client: TestClient):
    db = SessionLocal()
    try:
        db.merge(
            models.CompanySettings(
                company_id=CO,
                default_working_weekdays="[1,2,3,4,5]",
            )
        )
        db.commit()
        sat = date(2026, 5, 2)
        assert nearest_workday(sat, CO, db, direction="prev") == date(2026, 5, 1)
        assert next_business_day(date(2026, 5, 1), CO, db) == date(2026, 5, 4)
    finally:
        db.close()


def test_get_working_calendar_api(co_client: TestClient):
    db = SessionLocal()
    try:
        db.merge(
            models.CompanySettings(
                company_id=CO,
                default_working_weekdays="[1,2,3,4,5]",
            )
        )
        db.add(
            models.WorkingCalendar(
                company_id=CO,
                target_date=date(2026, 5, 3),
                is_working_day=False,
            )
        )
        db.commit()
    finally:
        db.close()

    r = co_client.get(
        "/v2/working-calendar",
        params={"company_id": CO, "month": "2026-05"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["default_working_weekdays"] == [1, 2, 3, 4, 5]
    assert len(body["days"]) == 31
    day3 = next(d for d in body["days"] if d["date"] == "2026-05-03")
    assert day3["is_working_day"] is False
    assert day3["source"] == "exception"
    assert any(e["target_date"] == "2026-05-03" for e in body["exceptions"])


def test_patch_working_days_api(co_client: TestClient):
    r = co_client.patch(
        "/v2/company-settings/working-days",
        json={
            "company_id": CO,
            "default_working_weekdays": [1, 2, 3, 4, 5],
            "exceptions": [
                {"target_date": "2026-05-04", "is_working_day": False},
                {"target_date": "2026-05-06", "is_working_day": True},
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["exception_count"] == 2

    r2 = co_client.get(
        "/v2/working-calendar",
        params={"company_id": CO, "month": "2026-05"},
    )
    assert r2.status_code == 200
    exc_dates = {e["target_date"]: e["is_working_day"] for e in r2.json()["exceptions"]}
    assert exc_dates["2026-05-04"] is False
    assert exc_dates["2026-05-06"] is True


def test_patch_working_days_auto_registers_company_master(client: TestClient):
    """新規 company_id でも営業日設定を保存できる（班長保存と同じ ensure ポリシー）。"""
    cid = "wd_auto_reg_co"
    r = client.patch(
        "/v2/company-settings/working-days",
        json={
            "company_id": cid,
            "default_working_weekdays": [1, 2, 3, 4, 5],
            "exceptions": [],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["company_id"] == cid

    masters = client.get("/admin/companies").json()
    hit = next((x for x in masters if x["company_id"] == cid), None)
    assert hit is not None
    assert hit["is_active"] is True


def test_patch_working_days_new_company_without_leaders_save(client: TestClient):
    """班長保存前でも営業日設定のみで master 登録・保存できる。"""
    cid = "test9_wd_only"
    r = client.patch(
        "/v2/company-settings/working-days",
        json={
            "company_id": cid,
            "default_working_weekdays": [1, 2, 3, 4, 5, 6],
            "exceptions": [{"target_date": "2026-06-10", "is_working_day": False}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["exception_count"] == 1

    r2 = client.get(
        "/v2/working-calendar",
        params={"company_id": cid, "month": "2026-06"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["default_working_weekdays"] == [1, 2, 3, 4, 5, 6]
