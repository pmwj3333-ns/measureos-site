"""
第5条仕様に基づく blue → red 昇格（テスト再判定 POST /v2/test/recompute から呼ぶ）。

- blue: 順序違反・乖離は即時、予告あり未実績は翌営業日 work_end 超過で（_apply_minimal_judgement）
- red: 「営業日の judgement_time」を**2回**跨いでも未解消のものだけ
  （1回目を跨いだだけでは blue のまま）

deadline_at（実装上の赤化閾値）:
  次の営業日の judgement_time を1回目、さらに次の営業日の同時刻を2回目とし、
  deadline_at = 2回目の日付 × judgement_time（JST）。
  営業日は company_calendar に従い next_business_day で進める。

参考: docs/measure-os-article-5-spec.md 「赤化条件」「deadline_at ルール」
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app import models
from app.services.business_date import calc_business_date, next_business_day
from app.services.status_history import (
    append_work_unit_status_history_if_changed,
    norm_work_unit_status,
)
from app.services.test_clock import reference_utc_now

JST = ZoneInfo("Asia/Tokyo")


def _as_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def reference_now_jst() -> datetime:
    """テストクロック対応の「いま」（JST aware）。"""
    ref_naive = _as_utc_naive(reference_utc_now())
    return ref_naive.replace(tzinfo=timezone.utc).astimezone(JST)


def _first_judgement_business_date(
    business_date: date,
    company_id: str,
    db: Session,
) -> date:
    return next_business_day(business_date, company_id, db)


def next_work_end_boundary_jst(
    business_date: date,
    work_end_time: time,
    company_id: str,
    db: Session,
) -> datetime:
    """
    未完了を青にする時刻（JST）: 当該 business_date の翌営業日 × work_end_time。
    営業時間内は未完了の可能性があるため、締め後に初めて青化する。
    """
    nd = _first_judgement_business_date(business_date, company_id, db)
    return datetime.combine(nd, work_end_time, tzinfo=JST)


def incomplete_implies_status_blue(
    *,
    has_planned_nonzero: bool,
    has_meaningful_actual: bool,
    business_date: date,
    company_id: str,
    settings: models.CompanySettings,
    db: Optional[Session],
) -> bool:
    """
    「予告あり・実績なし」（着手の有無は問わない）を status=blue にするか。
    「実績あり」は数量・明細ベース（_has_meaningful_actual）。actual_at のみでは未入力扱い。

    翌営業日の work_end を reference 時刻（JST）が跨いだときだけ True。
    """
    if not has_planned_nonzero or has_meaningful_actual:
        return False
    if db is None:
        return False
    wet: time = settings.work_end_time or time(17, 0)
    ref_jst = reference_now_jst()
    boundary = next_work_end_boundary_jst(business_date, wet, company_id, db)
    return ref_jst >= boundary


def compute_red_deadline_jst(
    business_date: date,
    judgement_time: time,
    company_id: str,
    db: Session,
) -> datetime:
    """
    営業日 business_date の行について、red 昇格の閾値となる日時（JST）。

    - 1回目の境界: next_business_day(D) の judgement_time
    - deadline_at （2回目）: next_business_day(1回目の日) の judgement_time
    """
    first_judgement_biz = _first_judgement_business_date(business_date, company_id, db)
    second_judgement_biz = next_business_day(first_judgement_biz, company_id, db)
    return datetime.combine(second_judgement_biz, judgement_time, tzinfo=JST)


def promote_blue_to_red_after_judgement(
    company_id: str,
    db: Session,
    *,
    ref_utc: Optional[datetime] = None,
) -> int:
    """
    status=blue の行で、参照時刻（JST）が deadline_at（2回目の judgement を跨いだ瞬間以降）なら red。

    judgement_time 未設定は 13:00 JST とみなす。
    """
    ref = ref_utc if ref_utc is not None else reference_utc_now()
    ref_naive = _as_utc_naive(ref)
    ref_jst = ref_naive.replace(tzinfo=timezone.utc).astimezone(JST)

    settings = (
        db.query(models.CompanySettings)
        .filter_by(company_id=company_id)
        .first()
    )
    if not settings:
        return 0

    jt: time = settings.judgement_time or time(13, 0)
    current_biz = calc_business_date(ref_naive, settings, db)

    units = (
        db.query(models.WorkUnit)
        .filter(models.WorkUnit.company_id == company_id)
        .all()
    )
    n = 0
    for unit in units:
        st = (unit.status or "").strip().lower()
        if st != "blue":
            continue
        if unit.business_date > current_biz:
            continue
        deadline_jst = compute_red_deadline_jst(unit.business_date, jt, company_id, db)
        if ref_jst >= deadline_jst:
            before = norm_work_unit_status(unit.status)
            unit.status = "red"
            unit.updated_at = datetime.utcnow()
            append_work_unit_status_history_if_changed(db, unit, before, "system")
            n += 1
    return n
