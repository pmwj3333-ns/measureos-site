"""
過去営業日の is_missing を再計算し、各行に _recompute_unit_derived を通す。
closed / red の行は work ルータ側で判定をスキップする。
"""
from sqlalchemy.orm import Session

from app import models
from app.services.business_date import calc_business_date
from app.services.test_clock import reference_utc_now


def _recompute_unit_derived(
    unit: models.WorkUnit, settings: models.CompanySettings, db: Session
) -> None:
    """flags・班長判定・status を一括更新（work ルータと同一、循環 import 回避で遅延 import）。"""
    from app.routers.work import _recompute_unit_derived as _main_recompute

    _main_recompute(unit, settings, db)


def recompute_is_missing_for_past_business_dates(
    company_id: str,
    db: Session,
    *,
    apply_derived: bool = True,
) -> int:
    """
    business_date < 現在営業日 の行について is_missing を再計算する。
    判定: planned_value / actual_value / started_at のいずれか欠ければ True。

    closed / red も is_missing は更新する（事後照会・red 化後の表示のため）。
    apply_derived が True のとき、各行について _recompute_unit_derived を実行する（本線・cron 用）。
    False のときは is_missing のみ更新する。POST /test/recompute は後段で全行を一度だけ
    _recompute するため False を指定し、二重 recompute による blue→normal 退行を防ぐ。
    戻り値: is_missing を式評価した行数（closed/red 含む）。
    """
    settings = (
        db.query(models.CompanySettings)
        .filter_by(company_id=company_id)
        .first()
    )
    if not settings:
        return 0

    current_biz = calc_business_date(reference_utc_now(), settings, db)
    units = (
        db.query(models.WorkUnit)
        .filter(
            models.WorkUnit.company_id == company_id,
            models.WorkUnit.business_date < current_biz,
        )
        .all()
    )

    n = 0
    for unit in units:
        n += 1
        unit.is_missing = (
            unit.planned_value is None
            or unit.actual_value is None
            or unit.started_at is None
        )
        if apply_derived:
            _recompute_unit_derived(unit, settings, db)
    return n
