from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ─── 会社設定 ───────────────────────────────────────────────
class CompanySettingsIn(BaseModel):
    company_id:        str
    company_name:      str = ""
    unit:              str = "個"
    tolerance_value:   int = 0
    day_boundary_time: Optional[str] = None   # "HH:MM"
    work_end_time:     Optional[str] = None
    judgement_time:    Optional[str] = None
    field_users:       Optional[str] = None   # 未指定なら既存を維持
    input_mode:        Optional[str] = None   # manufacturing | logistics。未指定なら既存を維持


class CompanySettingsOut(BaseModel):
    company_id:        str
    company_name:      str
    unit:              str
    tolerance_value:   int
    day_boundary_time: Optional[str]
    work_end_time:     Optional[str]
    judgement_time:    Optional[str]
    field_users:       str = ""
    input_mode:        str = "manufacturing"


class FieldUsersIn(BaseModel):
    company_id:   str
    field_users:  str = ""   # カンマ区切り（名前:工程 可）


# ─── カレンダー ─────────────────────────────────────────────
class CalendarIn(BaseModel):
    company_id: str
    date:       str   # "YYYY-MM-DD"
    is_workday: bool


# ─── WorkUnit ───────────────────────────────────────────────
class WorkUnitQuery(BaseModel):
    company_id:     str
    task_id:        str
    process_id:     str
    user_id:        str
    business_date:  Optional[str] = None  # YYYY-MM-DD。省略時はサーバが当日営業日を算出


class NextDayQuery(BaseModel):
    company_id:            str
    task_id:               str
    process_id:            str
    user_id:               str
    current_business_date: str   # "YYYY-MM-DD"


class WorkLineIn(BaseModel):
    """1行＝ラベル（商品名・対象名／作業内容）＋数量。不完全な行はクライアントで弾く想定。"""
    label: str = ""
    value: Optional[float] = None


class ActualIn(BaseModel):
    actual_value: Optional[float] = None
    actual_work_type: Optional[str] = None
    actual_work_label: Optional[str] = None
    actual_item_name: Optional[str] = None
    lines: Optional[List[WorkLineIn]] = None
    pattern_a: Optional[bool] = None
    pattern_b: Optional[bool] = None


class PlannedIn(BaseModel):
    planned_value: Optional[float] = None
    planned_work_type: Optional[str] = None
    planned_work_label: Optional[str] = None
    planned_item_name: Optional[str] = None
    lines: Optional[List[WorkLineIn]] = None


class DebugSetBusinessDateIn(BaseModel):
    """デバッグ専用: work_unit の business_date を手動変更（本番では使わない想定）。"""

    id: int
    business_date: str  # YYYY-MM-DD


class WorkLineOut(BaseModel):
    label: str
    value: float


class WorkUnitOut(BaseModel):
    id:                  int
    company_id:          str
    task_id:             str
    process_id:          str
    user_id:             str
    business_date:       str
    created_at:          Optional[str] = None
    business_date_source: Optional[str] = None
    business_date_debug: Optional[Dict[str, Any]] = None
    planned_work_type:   Optional[str] = None
    planned_work_label:  Optional[str] = None
    planned_item_name:   Optional[str] = None
    planned_lines:       Optional[List[WorkLineOut]] = None
    planned_value:       Optional[float]
    started_at:          Optional[str]
    actual_work_type:    Optional[str] = None
    actual_work_label:   Optional[str] = None
    actual_item_name:    Optional[str] = None
    actual_lines:        Optional[List[WorkLineOut]] = None
    actual_value:        Optional[float]
    actual_at:           Optional[str]
    pattern_a:           Optional[bool] = None
    pattern_b:           Optional[bool] = None
    status:              str = "normal"
    diff_value:          Optional[float]
    is_missing:          bool
    is_invalid_flow:     bool
    is_diff_anomaly:     bool
    is_unregistered_user: bool = False
    user_source:         str = "master"
    prev_planned_value:      Optional[float] = None
    prev_planned_work_type:  Optional[str] = None
    prev_planned_work_label: Optional[str] = None
    prev_planned_item_name:  Optional[str] = None
    prev_planned_lines:      Optional[List[WorkLineOut]] = None
    unit:                str = "個"               # 会社設定から取得
    input_mode:          str = "manufacturing"
