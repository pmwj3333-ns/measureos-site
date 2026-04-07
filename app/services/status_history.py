"""work_unit.status 変化の追記のみ（更新・削除なし）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def norm_work_unit_status(s: Optional[str]) -> str:
    """API / DB で使う status の正規化（比較・履歴保存用）。"""
    x = (s or "").strip().lower()
    if x in ("closed", "red", "blue", "normal"):
        return x
    return x if x else "normal"


def append_work_unit_status_history_if_changed(
    db: Session,
    unit: models.WorkUnit,
    status_before: str,
    trigger_type: str,
) -> None:
    """
    現在の unit.status が status_before と異なるときだけ 1 行追記する。
    同一 status の再計算では追加しない。
    """
    status_after = norm_work_unit_status(unit.status)
    if status_before == status_after:
        return
    uid = getattr(unit, "id", None)
    if uid is None:
        return
    db.add(
        models.WorkUnitStatusHistory(
            work_unit_id=uid,
            from_status=status_before,
            to_status=status_after,
            changed_at=datetime.utcnow(),
            trigger_type=trigger_type,
        )
    )
