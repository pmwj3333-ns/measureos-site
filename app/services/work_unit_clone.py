"""WorkUnit のコピー（append-only・同一キー複数行用）。"""

from __future__ import annotations

import json
import math
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
    unit.reflection_status = "pending"
    unit.reflection_reject_reason_code = None
    unit.reflection_reject_reason_detail = None
    if norm_work_unit_status(unit.status) not in ("closed", "red"):
        unit.status = "normal"


def work_unit_has_planned_facts(unit: models.WorkUnit) -> bool:
    """DB に保存された予告の事実（JSON・数量・レガシー項目）があるか。"""
    raw = getattr(unit, "planned_lines_json", None)
    if raw is not None and str(raw).strip():
        try:
            data = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            # 非 JSON でもカラムに文字が残っている＝予告の痕跡とみなす
            return True
        if isinstance(data, list) and len(data) > 0:
            return True
        if isinstance(data, dict) and data:
            return True
    pv = getattr(unit, "planned_value", None)
    if pv is not None:
        try:
            if math.isfinite(float(pv)):
                return True
        except (TypeError, ValueError):
            pass
    for attr in ("planned_item_name", "planned_work_label", "planned_work_type"):
        v = getattr(unit, attr, None)
        if v is not None and str(v).strip():
            return True
    return False


def sync_planned_at_with_planned_facts(unit: models.WorkUnit) -> None:
    """
    予告事実と planned_at の整合（append-only スナップショット用）。
    ・事実があり planned_at が null → 現在時刻（新規予告または旧不整合の修復）
    ・事実があり planned_at あり → 維持（clone による引き継ぎ）
    ・事実が無い → planned_at を null（明示的に予告を消した行の整合）
    """
    if not work_unit_has_planned_facts(unit):
        unit.planned_at = None
        return
    if unit.planned_at is None:
        unit.planned_at = datetime.utcnow()
