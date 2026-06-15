"""Package A: 営業日（working_calendar + default_working_weekdays）判定。"""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime
from typing import Dict, List, Literal, Optional, Tuple

from sqlalchemy.orm import Session

from app import models

FALLBACK_WEEKDAYS: Tuple[int, ...] = (1, 2, 3, 4, 5)


def parse_default_weekdays(raw: object) -> List[int]:
    """company_settings.default_working_weekdays を正規化（ISO: 月=1 … 日=7）。"""
    if raw is None or not str(raw).strip():
        return list(FALLBACK_WEEKDAYS)
    try:
        data = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return list(FALLBACK_WEEKDAYS)
    if not isinstance(data, list):
        return list(FALLBACK_WEEKDAYS)
    out: List[int] = []
    for x in data:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 7:
            out.append(n)
    out = sorted(set(out))
    return out if out else list(FALLBACK_WEEKDAYS)


def serialize_default_weekdays(weekdays: List[int]) -> str:
    valid = sorted({int(x) for x in weekdays if 1 <= int(x) <= 7})
    if not valid:
        valid = list(FALLBACK_WEEKDAYS)
    return json.dumps(valid)


def has_custom_default_weekdays(settings: Optional[models.CompanySettings]) -> bool:
    raw = getattr(settings, "default_working_weekdays", None) if settings else None
    return raw is not None and bool(str(raw).strip())


def get_default_weekdays(settings: Optional[models.CompanySettings]) -> List[int]:
    return parse_default_weekdays(
        getattr(settings, "default_working_weekdays", None) if settings else None
    )


def _exception_for_date(
    db: Session, company_id: str, target: date
) -> Optional[models.WorkingCalendar]:
    cid = (company_id or "").strip()
    if not cid:
        return None
    return (
        db.query(models.WorkingCalendar)
        .filter(
            models.WorkingCalendar.company_id == cid,
            models.WorkingCalendar.target_date == target,
        )
        .first()
    )


def working_day_source(
    company_id: str,
    target: date,
    db: Session,
    *,
    settings: Optional[models.CompanySettings] = None,
    exception: Optional[models.WorkingCalendar] = None,
) -> Literal["exception", "weekday", "fallback"]:
    exc = exception if exception is not None else _exception_for_date(db, company_id, target)
    if exc is not None:
        return "exception"
    st = settings
    if st is None:
        st = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if has_custom_default_weekdays(st):
        return "weekday"
    return "fallback"


def is_working_day(company_id: str, target: date, db: Session) -> bool:
    """
    営業日判定（優先順位）:
    1. working_calendar 例外
    2. default_working_weekdays
    3. fallback（月〜金）
    """
    cid = (company_id or "").strip()
    exc = _exception_for_date(db, cid, target)
    if exc is not None:
        return bool(exc.is_working_day)
    settings = db.query(models.CompanySettings).filter_by(company_id=cid).first()
    weekdays = get_default_weekdays(settings)
    return target.isoweekday() in weekdays


def list_exceptions(
    db: Session, company_id: str
) -> List[models.WorkingCalendar]:
    cid = (company_id or "").strip()
    return (
        db.query(models.WorkingCalendar)
        .filter(models.WorkingCalendar.company_id == cid)
        .order_by(
            models.WorkingCalendar.target_date.asc(),
            models.WorkingCalendar.id.asc(),
        )
        .all()
    )


def parse_month(month: str) -> Tuple[int, int]:
    s = (month or "").strip()
    parts = s.split("-")
    if len(parts) != 2:
        raise ValueError("month は YYYY-MM 形式です")
    year = int(parts[0])
    mon = int(parts[1])
    if mon < 1 or mon > 12:
        raise ValueError("month は YYYY-MM 形式です")
    return year, mon


def build_month_payload(company_id: str, month: str, db: Session) -> dict:
    cid = (company_id or "").strip()
    year, mon = parse_month(month)
    settings = db.query(models.CompanySettings).filter_by(company_id=cid).first()
    default_weekdays = get_default_weekdays(settings)
    exceptions = list_exceptions(db, cid)

    exc_by_date: Dict[date, models.WorkingCalendar] = {
        r.target_date: r for r in exceptions
    }

    _, last_day = calendar.monthrange(year, mon)
    days: List[dict] = []
    for day_num in range(1, last_day + 1):
        d = date(year, mon, day_num)
        exc = exc_by_date.get(d)
        src = working_day_source(cid, d, db, settings=settings, exception=exc)
        working = (
            bool(exc.is_working_day)
            if exc is not None
            else d.isoweekday() in default_weekdays
        )
        days.append(
            {
                "date": d.isoformat(),
                "weekday": d.isoweekday(),
                "is_working_day": working,
                "source": src,
            }
        )

    return {
        "company_id": cid,
        "month": f"{year:04d}-{mon:02d}",
        "default_working_weekdays": default_weekdays,
        "exceptions": [
            {
                "id": int(r.id),
                "target_date": r.target_date.isoformat(),
                "is_working_day": bool(r.is_working_day),
            }
            for r in exceptions
        ],
        "days": days,
    }


def save_working_days(
    db: Session,
    company_id: str,
    default_weekdays: List[int],
    exceptions: List[dict],
) -> dict:
    cid = (company_id or "").strip()
    settings = db.query(models.CompanySettings).filter_by(company_id=cid).first()
    if settings is None:
        settings = models.CompanySettings(company_id=cid)
        db.add(settings)
    settings.default_working_weekdays = serialize_default_weekdays(default_weekdays)

    db.query(models.WorkingCalendar).filter(
        models.WorkingCalendar.company_id == cid
    ).delete(synchronize_session=False)

    now = datetime.utcnow()
    seen_dates: set = set()
    for item in exceptions:
        ds = str(item.get("target_date") or "").strip()
        if not ds or ds in seen_dates:
            continue
        seen_dates.add(ds)
        d = date.fromisoformat(ds)
        db.add(
            models.WorkingCalendar(
                company_id=cid,
                target_date=d,
                is_working_day=bool(item.get("is_working_day")),
                created_at=now,
            )
        )
    db.commit()
    db.refresh(settings)
    return {
        "ok": True,
        "company_id": cid,
        "default_working_weekdays": get_default_weekdays(settings),
        "exception_count": len(seen_dates),
    }
