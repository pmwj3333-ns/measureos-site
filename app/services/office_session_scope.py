"""office / 現場 v2 共通: session company_id とリクエスト company の一致を強制。"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request

from app.services.company_validator import normalize_company_id


def get_session_company_id(request: Request) -> str:
    cid = normalize_company_id(request.session.get("company_id"))
    if not cid:
        raise HTTPException(status_code=401, detail="not authenticated")
    return cid


def require_session_company_match(request: Request, company_id: Optional[str]) -> str:
    """session company とリクエスト company_id が一致すること（不一致は 403）。"""
    session_cid = get_session_company_id(request)
    requested = normalize_company_id(company_id)
    if not requested:
        raise HTTPException(status_code=422, detail="company_id が空です")
    if requested != session_cid:
        raise HTTPException(status_code=403, detail="company_id does not match session")
    return session_cid


def require_session_company_row(request: Request, row_company_id: Optional[str]) -> str:
    """既存行の company_id が session と一致すること（不一致は 403）。"""
    session_cid = get_session_company_id(request)
    row_cid = normalize_company_id(row_company_id)
    if not row_cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    if row_cid != session_cid:
        raise HTTPException(status_code=403, detail="company_id does not match session")
    return session_cid
