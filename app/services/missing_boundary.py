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


def recompute_is_missing_for_past_business_dates(company_id: str, db: Session) -> int:
    """
    business_date < 現在営業日 の行について is_missing を再計算する。
    判定: planned_value / actual_value / started_at のいずれか欠ければ True。

    closed / red も is_missing は更新する（事後照会・red 化後の表示のため）。
    各行について _recompute_unit_derived を実行する（system_pattern / status を DB に反映）。
    これにより「再計算から除外していたせいで red の行だけ is_missing が常に false」の状態を避け、
    通常フロー（過去営業日 → 再計算で is_missing と blue → その後 red）でも整合する。
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
        _recompute_unit_derived(unit, settings, db)
    return n
