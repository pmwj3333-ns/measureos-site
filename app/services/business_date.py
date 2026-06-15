from datetime import datetime, date, time, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app import models
from app.services.working_calendar import is_working_day

# 営業日の暦日・境界時刻は常に Asia/Tokyo で解釈する（1社前提・固定）
JST = ZoneInfo("Asia/Tokyo")


def _as_utc_datetime(dt: datetime) -> datetime:
    """タイムゾーンなしの datetime は UTC とみなす。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calc_business_date_detailed(
    input_time: datetime, settings: models.CompanySettings, db: Session
) -> Tuple[date, Dict[str, Any]]:
    """
    calc_business_date と同じ結果の日付に加え、検証用のメタデータ dict を返す。
    """
    now_jst = _as_utc_datetime(input_time).astimezone(JST)
    local_date = now_jst.date()

    if settings.day_boundary_time:
        boundary_dt = datetime.combine(local_date, settings.day_boundary_time, tzinfo=JST)
        treat_prev = now_jst < boundary_dt
        candidate = local_date - timedelta(days=1) if treat_prev else local_date
        boundary_str = settings.day_boundary_time.isoformat()
        classification = "前日扱い" if treat_prev else "当日扱い"
    else:
        candidate = local_date
        boundary_str = None
        treat_prev = False
        classification = "境界未設定（JST当日を候補）"

    final = nearest_workday(candidate, settings.company_id, db, direction="prev")
    debug: Dict[str, Any] = {
        "timezone": "Asia/Tokyo",
        "now_jst": now_jst.isoformat(),
        "day_boundary_time": boundary_str,
        "jst_calendar_date": local_date.isoformat(),
        "treat_as_previous_local_day": treat_prev,
        "boundary_day_classification": classification,
        "candidate_before_calendar": candidate.isoformat(),
        "final_business_date": final.isoformat(),
    }
    return final, debug


def effective_calendar_date_jst(
    now_jst: datetime,
    day_boundary_time: Optional[time],
) -> date:
    """
    暦日 + day_boundary_time（第5条 A案）。
    JST 暦日の day_boundary 未満なら前暦日を effective とする。
    """
    local_date = now_jst.date()
    if day_boundary_time is None:
        return local_date
    now_t = now_jst.timetz().replace(tzinfo=None) if now_jst.tzinfo else now_jst.time()
    if now_t < day_boundary_time:
        return local_date - timedelta(days=1)
    return local_date


def calc_business_date(input_time: datetime, settings: models.CompanySettings, db: Session) -> date:
    """
    Asia/Tokyo の暦日・壁時計で business_date の候補日を決める。

    - input_time: 基準時刻。naive は UTC。aware は任意 TZ から JST に変換。
    - day_boundary_time: その JST 暦日のこの時刻「未満」なら前日を候補にする。
    - 未設定なら JST の当日を候補にする。
    - 候補が非営業日なら nearest_workday で直前の営業日へ（working_calendar 時間OS）。
    """
    return calc_business_date_detailed(input_time, settings, db)[0]


def calc_business_date_with_db(
    input_time: datetime, settings: models.CompanySettings, db: Session
) -> date:
    """互換名。work_units ルータ等からの呼び出し用（中身は calc_business_date と同一）。"""
    return calc_business_date(input_time, settings, db)


def nearest_workday(target: date, company_id: str, db: Session, direction: str = "prev") -> date:
    """
    target が非営業日なら direction に向かって最初の営業日を返す。
    営業日は working_calendar + default_working_weekdays（Package A 時間OS）。
    """
    current = target
    for _ in range(365):
        if is_working_day(company_id, current, db):
            return current
        current += timedelta(days=-1 if direction == "prev" else 1)
    return target


def next_business_day(from_date: date, company_id: str, db: Session) -> date:
    """from_date の翌日以降で最初の営業日を返す。"""
    return next_business_day_detailed(from_date, company_id, db)[0]


def next_business_day_detailed(
    from_date: date, company_id: str, db: Session
) -> Tuple[date, Dict[str, Any]]:
    """next_business_day と同結果に加え、カレンダー走査のメタデータを返す。"""
    next_cal = from_date + timedelta(days=1)
    final = nearest_workday(next_cal, company_id, db, direction="next")
    debug: Dict[str, Any] = {
        "timezone": "Asia/Tokyo",
        "from_business_date": from_date.isoformat(),
        "next_calendar_day_searched_from": next_cal.isoformat(),
        "final_business_date": final.isoformat(),
        "note": "POST /work/next-day: クライアントの current_business_date から翌営業日を算出",
    }
    return final, debug
