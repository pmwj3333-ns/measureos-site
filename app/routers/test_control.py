"""
テスト専用: 擬似 UTC・会社単位の再判定。本番では MEASUREOS_ALLOW_TEST_CLOCK を立てない。
現場 v2 の HTML には載せず、debug_v2 から利用する想定。
"""
from __future__ import annotations

import os
from datetime import datetime, time, timezone
from typing import Optional

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.business_date import calc_business_date
from app.services.judgement_promote import compute_red_deadline_jst
from app.services.status_history import (
    append_work_unit_status_history_if_changed,
    norm_work_unit_status,
)
from app.services.missing_boundary import recompute_is_missing_for_past_business_dates
from app.services.test_clock import (
    get_clock_state,
    parse_iso_to_naive_utc,
    reference_utc_now,
    set_reference_utc_naive,
)

_JST = ZoneInfo("Asia/Tokyo")

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


def _reference_to_jst_naive_pair(ref: Optional[datetime]) -> tuple:
    """reference_utc_now 相当の naive UTC と JST aware。"""
    r = ref if ref is not None else reference_utc_now()
    naive = r if r.tzinfo is None else r.astimezone(timezone.utc).replace(tzinfo=None)
    jst = naive.replace(tzinfo=timezone.utc).astimezone(_JST)
    return jst, naive


@router.post("/recompute")
def test_recompute(body: TestRecomputeBody, db: Session = Depends(get_db)):
    """
    テスト用の一括再判定。

    1) 過去営業日の is_missing + 従来の _recompute（本番同等）
    2) closed 以外は **既存 blue/red を一旦無視**：red を外してから _recompute_unit_derived で
       system_pattern 基準の blue/normal を再計算（red→blue 可）
    3) apply_judgement_red 時のみ、blue かつ参照時刻が judgement 2回目境界以上なら red。
       （API の judgement_red_deadline_at が null＝blue でないなら red にならない）
    """
    _require_test_clock()
    # work 参照は関数内で（import 周りの明確化）
    from app.routers.work import _get_or_create_settings, _recompute_unit_derived

    cid = body.company_id.strip()
    db.flush()
    n_miss = recompute_is_missing_for_past_business_dates(cid, db)

    settings = _get_or_create_settings(cid, db)
    ref_jst, ref_naive = _reference_to_jst_naive_pair(None)
    current_biz = calc_business_date(ref_naive, settings, db)
    jt: time = settings.judgement_time or time(13, 0)

    units = (
        db.query(models.WorkUnit).filter(models.WorkUnit.company_id == cid).all()
    )
    n_red_cleared = 0
    for unit in units:
        st = (unit.status or "").strip().lower()
        if st == "closed":
            continue
        if st == "red":
            before_clear = norm_work_unit_status(unit.status)
            unit.status = "normal"
            append_work_unit_status_history_if_changed(db, unit, before_clear, "system")
            n_red_cleared += 1
        _recompute_unit_derived(unit, settings, db)

    n_red = 0
    if body.apply_judgement_red:
        for unit in units:
            st = (unit.status or "").strip().lower()
            if st == "closed":
                continue
            if st != "blue":
                continue
            if unit.business_date > current_biz:
                continue
            deadline_jst = compute_red_deadline_jst(
                unit.business_date, jt, cid, db
            )
            if ref_jst >= deadline_jst:
                before_red = norm_work_unit_status(unit.status)
                unit.status = "red"
                unit.updated_at = datetime.utcnow()
                append_work_unit_status_history_if_changed(db, unit, before_red, "system")
                n_red += 1

    db.commit()
    return {
        "company_id": cid,
        "recomputed_past_business_date_rows": n_miss,
        "red_cleared_for_rejudge": n_red_cleared,
        "promoted_blue_to_red": n_red,
        "clock": get_clock_state(),
    }
