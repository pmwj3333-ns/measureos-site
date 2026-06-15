"""office_v2 会社ログイン（session に company_id のみ保持）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import OfficeLoginIn, OfficeSessionOut
from app.services.company_password import (
    company_has_password,
    get_company_master,
    verify_company_password,
)
from app.services.company_validator import normalize_company_id

router = APIRouter(prefix="/v2/office", tags=["v2-office-session"])

_LOGIN_FAIL = "会社IDまたはパスワードが正しくありません"


def _login_fail() -> HTTPException:
    return HTTPException(status_code=401, detail=_LOGIN_FAIL)


@router.post("/login", summary="office_v2 会社ログイン")
def office_login(body: OfficeLoginIn, request: Request, db: Session = Depends(get_db)):
    cid = normalize_company_id(body.company_id)
    password = str(body.password or "")
    if not cid or not password.strip():
        raise _login_fail()

    row = get_company_master(db, cid)
    if row is None or not bool(getattr(row, "is_active", True)):
        raise _login_fail()
    if not company_has_password(row):
        raise _login_fail()
    if not verify_company_password(password, row.company_password_hash):
        raise _login_fail()

    request.session["company_id"] = cid
    return {
        "company_id": cid,
        "company_name": (row.company_name or cid).strip(),
        "authenticated": True,
    }


@router.get("/session", response_model=OfficeSessionOut, summary="office_v2 session 確認")
def office_get_session(request: Request, db: Session = Depends(get_db)):
    cid = normalize_company_id(request.session.get("company_id"))
    if not cid:
        raise HTTPException(status_code=401, detail="not authenticated")

    row = get_company_master(db, cid)
    if row is None or not bool(getattr(row, "is_active", True)):
        request.session.clear()
        raise HTTPException(status_code=401, detail="not authenticated")

    return OfficeSessionOut(
        company_id=cid,
        company_name=(row.company_name or cid).strip(),
        authenticated=True,
    )


@router.post("/logout", summary="office_v2 ログアウト（session クリア）")
def office_logout(request: Request):
    request.session.clear()
    return {"ok": True}
