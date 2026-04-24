"""フェーズ1 v2 専用 API（sr_v2 / field_v2 / debug_v2 のみから利用。旧 /settings 非依存）"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.routers.settings import _parse_time, _time_str
from app.schemas import V2LeadersPut
from app.services.package_rules import (
    get_company_package,
    is_phase2_enabled,
    package_label,
)

router = APIRouter(prefix="/v2", tags=["v2-設定"])


def _norm_input_mode(raw) -> str:
    if not raw:
        return "manufacturing"
    x = str(raw).strip().lower()
    return "logistics" if x == "logistics" else "manufacturing"


@router.get("/companies", summary="登録済み company_id 一覧（v2）")
def v2_list_companies(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CompanySettings.company_id)
        .order_by(models.CompanySettings.company_id)
        .all()
    )
    return [{"company_id": r[0]} for r in rows]


@router.get("/company/{company_id}", summary="現場 v2 用・会社スナップショット")
def v2_get_company(company_id: str, db: Session = Depends(get_db)):
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if not s:
        return {
            "company_id": company_id,
            "company_name": "",
            "field_users": "",
            "input_mode": "manufacturing",
            "unit": "個",
            "day_boundary_time": None,
            "order_cutoff_time": None,
            "tolerance_value": None,
            "package_code": "A",
            "package_label": package_label("A"),
            "phase2_enabled": is_phase2_enabled(None),
        }
    pkg = get_company_package(s)
    return {
        "company_id": s.company_id,
        "company_name": (getattr(s, "company_name", None) or "").strip(),
        "field_users": (s.field_users or "").strip(),
        "input_mode": _norm_input_mode(getattr(s, "input_mode", None)),
        "unit": s.unit or "個",
        "day_boundary_time": _time_str(s.day_boundary_time),
        "order_cutoff_time": _time_str(getattr(s, "order_cutoff_time", None)),
        "tolerance_value": getattr(s, "tolerance_value", None),
        "package_code": pkg,
        "package_label": package_label(pkg),
        "phase2_enabled": is_phase2_enabled(s),
    }


@router.put("/company/{company_id}/leaders", summary="班長マスタを保存（v2・社労士 v2 専用）")
def v2_put_leaders(company_id: str, body: V2LeadersPut, db: Session = Depends(get_db)):
    parts: List[str] = []
    for e in body.leaders:
        n = (e.name or "").strip()
        if not n:
            continue
        p = (e.process or "").strip()
        parts.append(f"{n}:{p}" if p else n)
    raw = ",".join(parts)
    s = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
    if s is None:
        s = models.CompanySettings(company_id=company_id, package_code="A")
        db.add(s)
    s.field_users = raw
    if body.company_name is not None:
        s.company_name = (body.company_name or "").strip()
    if body.day_boundary_time is not None:
        t = (body.day_boundary_time or "").strip()
        if not t:
            s.day_boundary_time = None
        else:
            try:
                s.day_boundary_time = _parse_time(t)
            except (ValueError, AttributeError):
                raise HTTPException(
                    status_code=400,
                    detail="day_boundary_time は HH:MM 形式で指定してください（例: 05:00）",
                ) from None
    if "tolerance_value" in body.model_fields_set:
        s.tolerance_value = body.tolerance_value
    if "package_code" in body.model_fields_set and body.package_code is not None:
        pc = str(body.package_code).strip().upper()
        if pc not in ("A", "B", "C", "D"):
            raise HTTPException(
                status_code=400,
                detail="package_code は A / B / C / D のいずれかで指定してください",
            )
        s.package_code = pc
    if "order_cutoff_time" in body.model_fields_set:
        t = (body.order_cutoff_time or "").strip()
        if not t:
            s.order_cutoff_time = None
        else:
            try:
                s.order_cutoff_time = _parse_time(t)
            except (ValueError, AttributeError):
                raise HTTPException(
                    status_code=400,
                    detail="order_cutoff_time は HH:MM 形式で指定してください（例: 15:00）",
                ) from None
    db.commit()
    db.refresh(s)
    pkg = get_company_package(s)
    return {
        "company_id": company_id,
        "company_name": (getattr(s, "company_name", None) or "").strip(),
        "field_users": (s.field_users or "").strip(),
        "saved_count": len(parts),
        "day_boundary_time": _time_str(s.day_boundary_time),
        "order_cutoff_time": _time_str(getattr(s, "order_cutoff_time", None)),
        "tolerance_value": getattr(s, "tolerance_value", None),
        "package_code": pkg,
        "package_label": package_label(pkg),
        "phase2_enabled": is_phase2_enabled(s),
    }
