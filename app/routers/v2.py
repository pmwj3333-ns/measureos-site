"""フェーズ1 v2 専用 API（sr_v2 / field_v2 / debug_v2 のみから利用。旧 /settings 非依存）"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.routers.settings import _parse_time, _time_str
from app.schemas import V2CompanyCreateIn, V2CompanyCreateOut, V2CompanyPasswordReissueOut, V2LeadersPut
from app.services.package_rules import (
    get_company_package,
    is_phase2_enabled,
    package_bullets,
    package_description,
    package_display_code,
    package_label,
    package_tagline,
    package_targets,
)
from app.services.company_validator import ensure_company_registered, normalize_company_id, validate_company_id
from app.services.company_password import (
    company_has_password,
    get_company_master,
    hash_company_password,
    set_company_password_hash,
)
from app.services.company_provisioning import (
    generate_initial_password,
    generate_unique_company_id,
)

router = APIRouter(prefix="/v2", tags=["v2-設定"])


def _package_meta(pkg: str) -> dict:
    return {
        "package_code": pkg,
        "package_display_code": package_display_code(pkg),
        "package_label": package_label(pkg),
        "package_tagline": package_tagline(pkg),
        "package_description": package_description(pkg),
        "package_bullets": package_bullets(pkg),
        "package_targets": package_targets(pkg),
    }


def _norm_input_mode(raw) -> str:
    if not raw:
        return "manufacturing"
    x = str(raw).strip().lower()
    return "logistics" if x == "logistics" else "manufacturing"


def _password_meta(db: Session, company_id: str) -> dict:
    master = get_company_master(db, company_id)
    return {"has_password": company_has_password(master)}


def _validate_package_code(raw: str) -> str:
    pc = str(raw or "A").strip().upper()
    if pc not in ("A", "B", "C", "D"):
        raise HTTPException(
            status_code=400,
            detail="package_code は A / B / C / D のいずれかで指定してください",
        )
    return pc


@router.get("/companies", summary="登録済み company_id 一覧（v2）")
def v2_list_companies(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CompanySettings.company_id)
        .order_by(models.CompanySettings.company_id)
        .all()
    )
    return [{"company_id": r[0]} for r in rows]


@router.post(
    "/companies",
    response_model=V2CompanyCreateOut,
    summary="新規会社作成（company_id・初期パスワード自動生成）",
)
def v2_create_company(body: V2CompanyCreateIn, db: Session = Depends(get_db)):
    cname = (body.company_name or "").strip()
    if not cname:
        raise HTTPException(status_code=422, detail="company_name が空です")
    package_code = _validate_package_code(body.package_code)
    cid = generate_unique_company_id(db, cname)
    initial_password = generate_initial_password()
    now = datetime.utcnow()

    master = models.CompanyMaster(
        company_id=cid,
        company_name=cname,
        company_password_hash=hash_company_password(initial_password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(master)
    settings = models.CompanySettings(
        company_id=cid,
        company_name=cname,
        package_code=package_code,
    )
    db.add(settings)
    db.commit()

    return V2CompanyCreateOut(
        company_id=cid,
        company_name=cname,
        initial_password=initial_password,
        package_code=package_code,
        has_password=True,
    )


@router.post(
    "/company/{company_id}/password/reissue",
    response_model=V2CompanyPasswordReissueOut,
    summary="会社パスワード再発行（ランダム生成・平文はレスポンスのみ）",
)
def v2_reissue_company_password(company_id: str, db: Session = Depends(get_db)):
    cid = validate_company_id(db, company_id)
    initial_password = generate_initial_password()
    set_company_password_hash(db, cid, initial_password)
    db.commit()
    return V2CompanyPasswordReissueOut(
        company_id=cid,
        initial_password=initial_password,
        has_password=True,
    )


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
            "phase2_enabled": is_phase2_enabled(None),
            **_package_meta("A"),
            **_password_meta(db, company_id),
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
        "phase2_enabled": is_phase2_enabled(s),
        **_package_meta(pkg),
        **_password_meta(db, company_id),
    }


@router.put("/company/{company_id}/leaders", summary="班長マスタを保存（v2・社労士 v2 専用）")
def v2_put_leaders(company_id: str, body: V2LeadersPut, db: Session = Depends(get_db)):
    cid = normalize_company_id(company_id)
    master_name = (
        (body.company_name or "").strip()
        if body.company_name is not None
        else ""
    ) or cid
    ensure_company_registered(db, cid, company_name=master_name)
    parts: List[str] = []
    for e in body.leaders:
        n = (e.name or "").strip()
        if not n:
            continue
        p = (e.process or "").strip()
        parts.append(f"{n}:{p}" if p else n)
    raw = ",".join(parts)
    s = db.query(models.CompanySettings).filter_by(company_id=cid).first()
    if s is None:
        s = models.CompanySettings(company_id=cid, package_code="A")
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
        s.package_code = _validate_package_code(body.package_code)
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
    if "company_password" in body.model_fields_set:
        pwd = body.company_password
        if pwd is not None and str(pwd).strip():
            set_company_password_hash(db, cid, str(pwd))
    db.commit()
    db.refresh(s)
    pkg = get_company_package(s)
    return {
        "company_id": cid,
        "company_name": (getattr(s, "company_name", None) or "").strip(),
        "field_users": (s.field_users or "").strip(),
        "saved_count": len(parts),
        "day_boundary_time": _time_str(s.day_boundary_time),
        "order_cutoff_time": _time_str(getattr(s, "order_cutoff_time", None)),
        "tolerance_value": getattr(s, "tolerance_value", None),
        "phase2_enabled": is_phase2_enabled(s),
        **_package_meta(pkg),
        **_password_meta(db, cid),
    }
