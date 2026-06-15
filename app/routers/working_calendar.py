"""Package A: 営業日設定 API（v2 / sr_v2）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    WorkingCalendarMonthOut,
    WorkingDaysPatchIn,
    WorkingDaysPatchOut,
)
from app.services.company_validator import ensure_company_registered
from app.services.working_calendar import build_month_payload, save_working_days

router = APIRouter(prefix="/v2", tags=["v2-営業日"])


@router.get(
    "/working-calendar",
    response_model=WorkingCalendarMonthOut,
    summary="営業日カレンダー取得（Package A・定義・表示）",
)
def get_working_calendar(
    company_id: str = Query(..., description="company_id"),
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    try:
        return build_month_payload(cid, month.strip(), db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.patch(
    "/company-settings/working-days",
    response_model=WorkingDaysPatchOut,
    summary="基本営業曜日・例外日を更新（Package A・定義のみ）",
)
def patch_working_days(body: WorkingDaysPatchIn, db: Session = Depends(get_db)):
    cid = ensure_company_registered(db, body.company_id)
    weekdays = [int(x) for x in body.default_working_weekdays]
    if not weekdays or any(x < 1 or x > 7 for x in weekdays):
        raise HTTPException(
            status_code=422,
            detail="default_working_weekdays は 1〜7 の整数を1つ以上指定してください",
        )
    exceptions = [
        {
            "target_date": (e.target_date or "").strip(),
            "is_working_day": bool(e.is_working_day),
        }
        for e in body.exceptions
    ]
    for ex in exceptions:
        if not ex["target_date"]:
            continue
        try:
            from datetime import date as date_type

            date_type.fromisoformat(ex["target_date"])
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"例外日の形式が不正です: {ex['target_date']}",
            ) from e
    try:
        return save_working_days(db, cid, weekdays, exceptions)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
