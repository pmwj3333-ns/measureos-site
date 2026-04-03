"""
未入力 is_missing は「現在の営業日より前」の行に対してのみ更新する（フェーズ1）。

入力のたびに即 blue にしないため、calc_business_date(now) より前の business_date の行だけ
planned / actual / started の欠損を再評価し、status を同期する。

現場 API（/work/*）の各更新・一覧取得・POST /work/recalc-missing-boundary から呼ぶ。
closed/red は is_missing のみ更新し status は触らない。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.services.business_date import calc_business_date


def _sync_work_status(
    unit: models.WorkUnit, settings: models.CompanySettings, db: Session
) -> None:
    """work.routers.work._sync_work_status と同じルール（循環 import 回避のため複製）。"""
    cur = (unit.status or "normal").strip().lower()
    if cur in ("closed", "red"):
        return
    current_biz = calc_business_date(datetime.utcnow(), settings, db)
    past = unit.business_date < current_biz
    missing_counts = past and bool(unit.is_missing)
    if missing_counts or unit.is_invalid_flow or unit.is_diff_anomaly:
        unit.status = "blue"
    else:
        unit.status = "normal"


def recompute_is_missing_for_past_business_dates(company_id: str, db: Session) -> int:
    """
    business_date < 現在営業日 の行について is_missing を再計算する。
    判定: planned_value / actual_value / started_at のいずれか欠ければ True。

    closed / red も is_missing は更新する（事後照会・red 化後の表示のため）。
    ただし _sync_work_status は呼ばないので status は上書きしない。
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

    current_biz = calc_business_date(datetime.utcnow(), settings, db)
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
        st = (unit.status or "normal").strip().lower()
        if st not in ("closed", "red"):
            _sync_work_status(unit, settings, db)
    return n
