"""
過去営業日の is_missing バッチ（旧実装）。

append-only 方針のため本線では呼び出さず、派生値は読み取り時に算出する。
"""

from sqlalchemy.orm import Session


def recompute_is_missing_for_past_business_dates(
    company_id: str,
    db: Session,
    *,
    apply_derived: bool = True,
) -> int:
    """互換 API。過去 work_unit を UPDATE しない（常に 0 を返す）。"""
    _ = company_id
    _ = db
    _ = apply_derived
    return 0
