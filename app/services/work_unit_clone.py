"""WorkUnit のコピー（append-only・同一キー複数行用）。"""

from __future__ import annotations

from datetime import datetime

from app import models
from app.services.status_history import norm_work_unit_status


def clone_work_unit_row(source: models.WorkUnit) -> models.WorkUnit:
    nu = models.WorkUnit()
    for col in models.WorkUnit.__table__.columns:
        key = col.key
        if key == "id":
            continue
        setattr(nu, key, getattr(source, key))
    nu.created_at = datetime.utcnow()
    nu.updated_at = None
    return nu


def strip_derived_columns_for_fact_snapshot(unit: models.WorkUnit) -> None:
    """INSERT するスナップショットから派生フィールドを落とす（DB は事実のみ）。"""
    unit.is_missing = False
    unit.is_invalid_flow = False
    unit.is_diff_anomaly = False
    unit.system_pattern = None
    unit.anomaly_started_at = None
    unit.is_unregistered_user = False
    unit.user_source = "master"
    if norm_work_unit_status(unit.status) not in ("closed", "red"):
        unit.status = "normal"
