from datetime import time
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["設定"])


def _time_str(t) -> Optional[str]:
    return t.strftime("%H:%M") if t else None


def _parse_time(s: Optional[str]):
    if not s:
        return None
    h, m = s.split(":")
    return time(int(h), int(m))


def _norm_input_mode(raw) -> str:
    if not raw:
        return "manufacturing"
    x = str(raw).strip().lower()
    return "logistics" if x == "logistics" else "manufacturing"


def _to_out(s: models.CompanySettings) -> dict:
    return {
        "company_id":        s.company_id,
        "company_name":      s.company_name or "",
        "unit":              s.unit or "個",
        "tolerance_value":   int(s.tolerance_value or 0),
        "day_boundary_time": _time_str(s.day_boundary_time),
        "work_end_time":     _time_str(s.work_end_time),
        "judgement_time":    _time_str(s.judgement_time),
        "field_users":       (s.field_users or "").strip(),
        "input_mode":        _norm_input_mode(getattr(s, "input_mode", None)),
    }


def _default_settings_out(company_id: str) -> dict:
    return {
        "company_id":        company_id,
        "company_name":      "",
        "unit":              "個",
        "tolerance_value":   0,
        "day_boundary_time": "00:00",
        "work_end_time":     "17:00",
        "judgement_time":    "13:00",
        "field_users":       "",
        "input_mode":        "manufacturing",
    }


@router.get("/settings/companies", summary="登録済み企業ID一覧")
def list_companies(db: Session = Depends(get_db)):
    rows = db.query(models.CompanySettings.company_id).order_by(models.CompanySettings.company_id).all()
    return [{"company_id": r[0]} for r in rows]


@router.post("/settings/field-users", summary="班長リストのみ保存する")
def save_field_users(body: schemas.FieldUsersIn, db: Session = Depends(get_db)):
    s = db.query(models.CompanySettings).filter_by(company_id=body.company_id).first()
    if s is None:
        s = models.CompanySettings(company_id=body.company_id)
        db.add(s)
    s.field_users = body.field_users or ""
    db.commit()
    db.refresh(s)
    return _to_out(s)


@router.post("/settings", summary="会社設定を保存する")
def save_settings(body: schemas.CompanySettingsIn, db: Session = Depends(get_db)):
    s = db.query(models.CompanySettings).filter_by(company_id=body.company_id).first()
    if s is None:
        s = models.CompanySettings(company_id=body.company_id)
        db.add(s)
    s.company_name      = body.company_name
    s.unit              = body.unit
    s.tolerance_value   = body.tolerance_value
    s.day_boundary_time = _parse_time(body.day_boundary_time)
    s.work_end_time     = _parse_time(body.work_end_time)
    s.judgement_time    = _parse_time(body.judgement_time)
    if body.field_users is not None:
        s.field_users = body.field_users
    if body.input_mode is not None:
        s.input_mode = _norm_input_mode(body.input_mode)
    db.commit()
    db.refresh(s)
    return _to_out(s)


@router.get("/settings/{company_id}", summary="会社設定を取得する")
def get_settings(company_id: str, db: Session = Depends(get_db)):
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if not s:
        return _default_settings_out(company_id)
    return _to_out(s)


@router.post("/calendar", summary="カレンダーを登録する")
def save_calendar(body: schemas.CalendarIn, db: Session = Depends(get_db)):
    from datetime import date as date_type
    d = date_type.fromisoformat(body.date)
    record = db.query(models.CompanyCalendar).filter_by(
        company_id=body.company_id, date=d
    ).first()
    if record is None:
        record = models.CompanyCalendar(company_id=body.company_id, date=d)
        db.add(record)
    record.is_workday = body.is_workday
    db.commit()
    return {"ok": True, "date": body.date, "is_workday": body.is_workday}
