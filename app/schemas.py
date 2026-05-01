from pydantic import BaseModel, Field
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


# ─── v2 班長マスタ（sr_v2 / PUT leaders）──────────────────────
class V2LeaderRow(BaseModel):
    name: str = ""
    process: str = ""


class V2LeadersPut(BaseModel):
    leaders: List[V2LeaderRow] = Field(default_factory=list)
    day_boundary_time: Optional[str] = Field(
        default=None,
        description="HH:MM。省略時は day_boundary_time を変更しない。",
    )
    company_name: Optional[str] = Field(
        default=None,
        description="表示用会社名。省略時は company_name を変更しない。",
    )
    tolerance_value: Optional[int] = Field(
        default=None,
        description="数値乖離の許容差（±）。省略時は tolerance_value を変更しない。",
    )
    package_code: Optional[str] = Field(
        default=None,
        description="Package A|B|C|D。省略時は package_code を変更しない。",
    )
    order_cutoff_time: Optional[str] = Field(
        default=None,
        description="HH:MM。第7条・3条の受注締切。unset で変更しない。空文字でクリア。",
    )


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
    """One planned line: label, quantity, optional line_id (stable row id), optional due_date."""
    label: str = ""
    value: Optional[float] = None
    line_id: Optional[str] = None
    due_date: Optional[str] = None
    product_code: Optional[str] = None


class ActualIn(BaseModel):
    actual_value: Optional[float] = None
    actual_work_type: Optional[str] = None
    actual_work_label: Optional[str] = None
    actual_item_name: Optional[str] = None
    lines: Optional[List[WorkLineIn]] = None
    pattern_a: Optional[bool] = None
    pattern_b: Optional[bool] = None
    # 現場チェック B のみ（"B" / null）。system_pattern とは独立
    user_pattern: Optional[str] = None
    # 第7条逸脱（予定外ラベル）のときのみ必須。逸脱でないときは送らずサーバがクリアする。
    deviation_reason: Optional[str] = None


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
    line_id: Optional[str] = None
    due_date: Optional[str] = None  # YYYY-MM-DD
    product_code: Optional[str] = None


class PlannedDueMergeEntry(BaseModel):
    """PATCH planned line due_date by line_id (POST .../planned-due)."""

    line_id: str
    due_date: Optional[str] = None


class PlannedDueMergeIn(BaseModel):
    """Merge due_date onto planned rows matched by line_id (office / debug)."""

    entries: List[PlannedDueMergeEntry] = Field(default_factory=list)


# ─── 第7条フェーズ1・priority_item（work_unit 非依存）────────────────

class PriorityItemIn(BaseModel):
    label: str = ""
    ship_value: Optional[float] = None
    prod_value: Optional[float] = None
    due_date: Optional[str] = None


class PriorityItemsCreateIn(BaseModel):
    company_id: str
    items: List[PriorityItemIn] = Field(default_factory=list)


class PriorityItemOut(BaseModel):
    id: int
    product_code: str = ""
    label: str
    ship_value: float
    stock_qty: float = 0
    prod_value: float
    due_date: Optional[str] = None
    status: str = "open"
    # 第7条フェーズ1・在庫×出荷×納期から算出（CSV再生成・手入力どちらも GET 時に同じ式）
    priority_level: str = "low"
    priority_score: float = 0.0
    # Package A: 第5条（WorkUnit 実績）から付与する表示のみ。第7条の数量は変更しない。
    article7_actual_hint: Optional[str] = None
    article7_notices: List[str] = Field(default_factory=list)


class PriorityItemsOut(BaseModel):
    items: List[PriorityItemOut] = Field(default_factory=list)


class PriorityRebuildIn(BaseModel):
    company_id: str


class PriorityRebuildOut(BaseModel):
    """POST /v2/priority/rebuild（在庫×出荷予定から第7条再生成）。"""

    ok: bool = True
    success_count: int = 0
    warning_count: int = Field(
        0,
        description=(
            "在庫未登録・コード空欄・不要（在庫で賄う）・納期不正などの件数の合算（参考）。"
        ),
    )
    detail: Optional[str] = Field(
        None,
        description="警告の内訳を1行にまとめた文言（該当なしは null）。",
    )


class PriorityCloseIn(BaseModel):
    company_id: str
    item_ids: List[int] = Field(..., min_length=1)


class PriorityCloseOut(BaseModel):
    ok: bool = True
    closed_count: int = 0


# ─── 商品マスタ（第5条・product_code 補完）──────────────────────────

class ProductMasterOut(BaseModel):
    id: int
    company_id: str
    product_code: Optional[str] = None
    label: str
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductMasterEnsureIn(BaseModel):
    company_id: str
    label: str


class ProductMasterPatchIn(BaseModel):
    product_code: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None


class StockImportOut(BaseModel):
    """POST /v2/stock/import の応答（在庫CSV・会社単位全置換）。"""

    ok: bool = True
    success_count: int = 0
    error_count: int = 0


class ShipmentImportOut(BaseModel):
    """POST /v2/shipment/import の応答（出荷予定CSV・会社単位全置換）。"""

    ok: bool = True
    success_count: int = Field(
        0,
        description=(
            "最終的に保存されたユニーク件数（product_code + due_date 単位）。"
            "同一キーの重複行は後勝ちで1件にまとめた後の件数。"
        ),
    )
    error_count: int = 0


class WorkUnitStatusHistoryItem(BaseModel):
    """work_unit_status_history 1行（読み取り専用）。"""

    id: int
    from_status: Optional[str] = None
    to_status: str
    changed_at: Optional[str] = None
    trigger_type: Optional[str] = None


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
    user_pattern:        Optional[str] = None  # 現場申告 B のみ（未申告は null）。system_pattern とは独立
    system_pattern:      str = ""  # 第5条フェーズ1・サーバ確定 A*/B*（user_pattern とは独立）
    status:              str = "normal"
    judgement_red_deadline_at: Optional[str] = None  # フェーズ2かつ blue 時: 2回目 judgement 境界（ISO）
    diff_value:          Optional[float]
    is_missing:          bool
    is_invalid_flow:     bool
    is_diff_anomaly:     bool
    anomaly_started_at:  Optional[str] = None
    is_unregistered_user: bool = False
    user_source:         str = "master"
    prev_planned_value:      Optional[float] = None
    prev_planned_work_type:  Optional[str] = None
    prev_planned_work_label: Optional[str] = None
    prev_planned_item_name:  Optional[str] = None
    prev_planned_lines:      Optional[List[WorkLineOut]] = None
    unit:                str = "個"               # 会社設定から取得
    input_mode:          str = "manufacturing"
    is_deviation:        bool = False
    is_article7_deviation: bool = False
    deviation_reason:    Optional[str] = None
    office_chain_hint:   str = ""
