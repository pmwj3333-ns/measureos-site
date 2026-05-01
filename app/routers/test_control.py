"""
テスト専用: 擬似 UTC・会社単位の再判定。本番では MEASUREOS_ALLOW_TEST_CLOCK を立てない。
現場 v2 の HTML には載せず、debug_v2 から利用する想定。
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.judgement_promote import promote_blue_to_red_after_judgement
from app.services.package_rules import get_company_package, is_phase2_enabled
from app.services.test_clock import (
    get_clock_state,
    parse_iso_to_naive_utc,
    set_reference_utc_naive,
)

router = APIRouter(prefix="/test", tags=["v2-テスト専用・擬似時刻"])


def _test_clock_allowed() -> bool:
    return os.environ.get("MEASUREOS_ALLOW_TEST_CLOCK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _require_test_clock() -> None:
    if not _test_clock_allowed():
        raise HTTPException(
            status_code=404,
            detail="テスト用 API は無効です。起動時に MEASUREOS_ALLOW_TEST_CLOCK=1 を設定してください。",
        )


@router.get("/clock")
def test_clock_get():
    """
    常に 200。debug_v2 から接続先の診断用（本番でも環境変数の有無だけ返る）。
    """
    allowed = _test_clock_allowed()
    state = get_clock_state()
    server_utc = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return {
        "test_clock_api_enabled": allowed,
        "server_utc_iso": server_utc,
        "active": state["active"],
        "utc_iso": state["utc_iso"],
    }


class TestClockPost(BaseModel):
    clear: bool = False
    utc_iso: Optional[str] = None


@router.post("/clock")
def test_clock_post(body: TestClockPost):
    _require_test_clock()
    if body.clear:
        set_reference_utc_naive(None)
        return {**get_clock_state(), "message": "cleared"}
    if not body.utc_iso or not str(body.utc_iso).strip():
        raise HTTPException(
            status_code=422,
            detail="utc_iso（例: 2026-04-04T06:00:00Z）または clear:true を指定してください",
        )
    try:
        naive = parse_iso_to_naive_utc(body.utc_iso)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=422,
            detail=f"utc_iso が解釈できません: {e}",
        ) from e
    set_reference_utc_naive(naive)
    return {**get_clock_state(), "message": "set"}


class TestRecomputeBody(BaseModel):
    company_id: str = Field(..., min_length=1)
    apply_judgement_red: bool = True


@router.post("/recompute")
def test_recompute(body: TestRecomputeBody, db: Session = Depends(get_db)):
    """
    append-only のため既存 work_unit は書き換えない。
    apply_judgement_red が真かつフェーズ2 Package のときのみ blue→red の INSERT を試みる。
    """
    _require_test_clock()
    from app.routers.work import _get_or_create_settings

    cid = body.company_id.strip()
    settings = _get_or_create_settings(cid, db)

    n_red = 0
    if body.apply_judgement_red:
        n_red = promote_blue_to_red_after_judgement(cid, db)

    phase2_on = is_phase2_enabled(settings)

    db.commit()
    return {
        "company_id": cid,
        "note": "append_only_no_bulk_derived_updates",
        "recomputed_past_business_date_rows": 0,
        "red_cleared_for_rejudge": 0,
        "promoted_blue_to_red": n_red,
        "phase2_enabled": phase2_on,
        "package_code": get_company_package(settings),
        "judgement_red_skipped": bool(body.apply_judgement_red and not phase2_on),
        "clock": get_clock_state(),
    }
