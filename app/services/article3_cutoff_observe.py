"""第3条 Package A: 締切後投入の観測（制御・due_date 変更は行わない）。"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from app.services.article3_priority_due import ordered_at_to_jst
from app.services.business_date import JST


def is_after_order_cutoff(
    created_at: Optional[datetime],
    order_cutoff: Optional[time],
) -> bool:
    """
    company_settings.order_cutoff_time（受注締切・第3条）を JST 暦日で超えて
    priority_item が生成されたか。未設定締切は常に False（観測スキップ）。
    """
    if order_cutoff is None or created_at is None:
        return False
    jst = ordered_at_to_jst(created_at)
    if jst is None:
        return False
    cutoff_dt = datetime.combine(jst.date(), order_cutoff, tzinfo=JST)
    return jst > cutoff_dt
