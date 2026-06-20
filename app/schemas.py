from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal


# ─── company_master（管理用・第1段階）────────────────────────
class CompanyMasterCreateIn(BaseModel):
    company_id: str
    company_name: str


class CompanyMasterPatchIn(BaseModel):
    company_name: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyMasterOut(BaseModel):
    id: int
    company_id: str
    company_name: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
        description="結果不備判定の許容差（±）。省略時は tolerance_value を変更しない。",
    )
    package_code: Optional[str] = Field(
        default=None,
        description="Package A|B|C|D。省略時は package_code を変更しない。",
    )
    order_cutoff_time: Optional[str] = Field(
        default=None,
        description="HH:MM。第7条・3条の受注締切。unset で変更しない。空文字でクリア。",
    )
    company_password: Optional[str] = Field(
        default=None,
        description="会社パスワード（平文）。省略または空のときは変更しない。",
    )


class V2CompanyCreateIn(BaseModel):
    company_name: str
    package_code: str = "A"


class V2CompanyCreateOut(BaseModel):
    company_id: str
    company_name: str
    initial_password: str
    package_code: str
    has_password: bool = True


class V2CompanyPasswordReissueOut(BaseModel):
    company_id: str
    initial_password: str
    has_password: bool = True


class OfficeLoginIn(BaseModel):
    company_id: str
    password: str


class OfficeSessionOut(BaseModel):
    company_id: str
    company_name: str
    authenticated: bool = True


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


class UsedMaterialIn(BaseModel):
    """第5条・実績に付随する使用物ログ（任意・記録のみ。product_code なし）。"""

    label: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None
    lot_no: Optional[str] = None


class UsedMaterialOut(BaseModel):
    label: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None
    lot_no: Optional[str] = None


class WorkLineIn(BaseModel):
    """One planned line: label, quantity, optional line_id (stable row id), optional due_date."""
    label: str = ""
    value: Optional[float] = None
    line_id: Optional[str] = None
    due_date: Optional[str] = None
    product_code: Optional[str] = None
    # 実績行のみ。現場メモ（引継ぎ・補足）。予告保存時はサーバ側で保持しない。
    line_memo: Optional[str] = None
    # 実績（actual lines）のみ利用。予告では無視される。任意・記録のみ。
    used_materials: Optional[List[UsedMaterialIn]] = None


class AnomalyClassificationIn(BaseModel):
    """第5条: 現場 A/B 中分類（Package A 任意）。"""

    process: List[str] = Field(default_factory=list)
    result: List[str] = Field(default_factory=list)


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
    anomaly_classification: Optional[AnomalyClassificationIn] = None
    # 第7条逸脱（予定外ラベル）のときのみ必須。逸脱でないときは送らずサーバがクリアする。
    deviation_reason: Optional[str] = None
    # 現場・実績時のみ任意（誤入力説明・補足）
    actual_memo: Optional[str] = None
    # 使用物ログ（原料・備品・ロット等）。省略時はサーバ側でクリア。空配列も可。
    used_materials: Optional[List[UsedMaterialIn]] = None


class PlannedIn(BaseModel):
    planned_value: Optional[float] = None
    planned_work_type: Optional[str] = None
    planned_work_label: Optional[str] = None
    planned_item_name: Optional[str] = None
    lines: Optional[List[WorkLineIn]] = None


class StartedIn(BaseModel):
    """POST /work/{id}/start 用。planned_registered_at 必須（予告フェーズ通過後のみ着手可）。body.lines は互換用で通常は送らない。"""

    lines: Optional[List[WorkLineIn]] = None


class DebugSetBusinessDateIn(BaseModel):
    """デバッグ専用: work_unit の business_date を手動変更（本番では使わない想定）。"""

    id: int
    business_date: str  # YYYY-MM-DD


class WorkLineOut(BaseModel):
    label: str
    value: Optional[float] = None
    line_id: Optional[str] = None
    due_date: Optional[str] = None  # YYYY-MM-DD
    product_code: Optional[str] = None
    line_memo: Optional[str] = None
    used_materials: Optional[List[UsedMaterialOut]] = None


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
    # 第7条・商品マスタ基準在庫（GET 時に付与。NULL=未設定・計算は0）
    safety_stock_value: Optional[int] = None
    safety_stock_unset: bool = False
    usable_stock_qty: float = 0
    is_after_cutoff: bool = False
    status: str = "open"
    # 第7条フェーズ1・在庫×出荷×納期から算出（CSV再生成・手入力どちらも GET 時に同じ式）
    priority_level: str = "low"
    priority_score: float = 0.0
    # Package A: 第5条（WorkUnit 実績）から付与する表示のみ。第7条の数量は変更しない。
    article7_actual_hint: Optional[str] = None
    article7_notices: List[str] = Field(default_factory=list)
    # GET ?article5_progress=1 のときのみ。現場第5条画面の進捗表示用（優先順位一覧では未使用）。
    article5_completed_qty: Optional[float] = Field(
        None,
        description="第5条・actual_at あり実績を商品一致で集計した累計数量（参考・第7条は更新しない）。",
    )
    article5_remaining_qty: Optional[float] = Field(
        None,
        description="max(0, prod_value - article5_completed_qty)。現場向け製造残（作成済み ✔ は残り<=0 で判定）。",
    )
    article5_effective_usable_qty: Optional[float] = Field(
        None,
        description="stock_qty + article5_completed_qty。在庫CSVに作成済み実績を加えた使用可能在庫（表示のみ）。",
    )
    article5_margin_after_ship_qty: Optional[float] = Field(
        None,
        description=(
            "article5_effective_usable_qty - ship_value - safety_stock_value。"
            "基準在庫を残した出荷後余裕（表示のみ）。"
        ),
    )
    # GET 時に PriorityItem の stock / ship / prod から算出（表示のみ・prod_value は変更しない）
    shortage_from_ship_qty: float = Field(
        0.0,
        description="不足内訳・出荷不足分 max(0, ship_value - stock_qty)。",
    )
    shortage_from_safety_qty: float = Field(
        0.0,
        description="不足内訳・基準在庫不足分 max(0, prod_value - shortage_from_ship_qty)。",
    )
    shortage_reason_labels: List[str] = Field(
        default_factory=list,
        description='不足理由ラベル（例: ["出荷不足", "基準在庫不足"]）。手入力行は ["出荷不足（手入力）"]。',
    )
    # product_master.production_mode を参照（表示分離用・不足計算は共通）
    production_mode: str = "manufacture"


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
    safety_stock_value: Optional[int] = None
    production_mode: str = "manufacture"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductMasterEnsureIn(BaseModel):
    company_id: str
    label: str


class ProductMasterCreateIn(BaseModel):
    """POST /v2/product-master（重複 label は 422。ensure は GET 相当の冪等作成）。"""

    company_id: str
    label: str


class ProductMasterPatchIn(BaseModel):
    product_code: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None
    safety_stock_value: Optional[int] = None
    production_mode: Optional[Literal["manufacture", "purchase"]] = None


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


class OfficeReflectionPatch(BaseModel):
    """事務画面・反映判断のみ更新（異常判定・status は変更しない）。"""

    reflection_status: Literal["pending", "accepted", "rejected"]
    reject_reason_code: Optional[str] = Field(
        None,
        description="rejected 時のみ。input_error | outside_instruction | other",
    )
    reject_reason_detail: Optional[str] = Field(
        None, description="その他理由や補足（other 選択時は推奨）"
    )


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
    planned_at:          Optional[str] = None
    planned_registered_at: Optional[str] = None  # 「予告を登録」確定時のみ
    planned_lines:       Optional[List[WorkLineOut]] = None
    planned_value:       Optional[float]
    started_at:          Optional[str]
    actual_work_type:    Optional[str] = None
    actual_work_label:   Optional[str] = None
    actual_item_name:    Optional[str] = None
    actual_lines:        Optional[List[WorkLineOut]] = None
    actual_value:        Optional[float]
    actual_at:           Optional[str]
    actual_memo:         Optional[str] = None
    used_materials:      Optional[List[UsedMaterialOut]] = None
    used_materials_json: Optional[str] = None
    pattern_a:           Optional[bool] = None
    pattern_b:           Optional[bool] = None
    user_pattern:        Optional[str] = None  # 現場申告 B のみ（未申告は null）。system_pattern とは独立
    anomaly_classification: Optional[AnomalyClassificationIn] = None
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
    reflection_status: str = "pending"
    reflection_reject_reason_code: Optional[str] = None
    reflection_reject_reason_detail: Optional[str] = None
    office_chain_hint:   str = ""
    is_actual_revision: bool = False
    actual_revision_detail_line: Optional[str] = None
    actual_revision_notice_strong: bool = False


class PackageAObserveSummaryOut(BaseModel):
    blue_count: int = 0
    after_cutoff_count: int = 0
    prev_day_incomplete_count: int = 0
    planned_unstarted_count: int = 0
    diff_anomaly_count: int = 0
    exception_input_count: int = 0


class PackageAObserveAnomalyRowOut(BaseModel):
    observed_at: str = ""
    time_label: str = ""
    leader: str = ""
    process_id: str = ""
    kind: str = ""
    content: str = ""
    business_date: str = ""


class PackageAObserveProcessRowOut(BaseModel):
    process_id: str = ""
    blue_count: int = 0
    blue_rate: float = 0.0
    after_cutoff_count: int = 0
    incomplete_count: int = 0
    total_count: int = 0


class PackageAObservePriorityStatusOut(BaseModel):
    shortage_count: int = 0
    after_cutoff_count: int = 0
    safety_unset_count: int = 0
    concentration_label: str = ""
    open_item_count: int = 0
    manufacture_shortage_count: int = 0
    purchase_shortage_count: int = 0


class FieldClassificationBreakdownRowOut(BaseModel):
    code: str
    label: str
    count: int


class FieldClassificationBreakdownOut(BaseModel):
    note: str = ""
    display_mode: str = "empty"
    process: List[FieldClassificationBreakdownRowOut] = Field(default_factory=list)
    result: List[FieldClassificationBreakdownRowOut] = Field(default_factory=list)
    auto_process: Optional[FieldClassificationBreakdownRowOut] = None
    auto_result: Optional[FieldClassificationBreakdownRowOut] = None


class PackageAObserveDashboardOut(BaseModel):
    company_id: str
    generated_at: str
    current_business_date: str
    summary: PackageAObserveSummaryOut
    recent_anomalies: List[PackageAObserveAnomalyRowOut]
    process_observation: List[PackageAObserveProcessRowOut]
    priority_status: PackageAObservePriorityStatusOut
    field_classification_breakdown: FieldClassificationBreakdownOut = Field(
        default_factory=FieldClassificationBreakdownOut
    )


class PackageAObservePortfolioCompanyOut(BaseModel):
    company_id: str
    company_name: str
    blue_count: int = 0
    blue_rate: float = 0.0
    last_activity_at: Optional[str] = None
    status: str = "normal"
    danger_score: int = 0
    weekly_report_target: bool = False
    prev_day_incomplete_count: int = 0
    after_cutoff_count: int = 0
    planned_unstarted_count: int = 0
    diff_anomaly_count: int = 0
    exception_input_count: int = 0


class PackageAObservePortfolioTotalsOut(BaseModel):
    company_count: int = 0
    danger_count: int = 0
    watch_count: int = 0
    normal_count: int = 0


class PackageAObservePortfolioBlueRateItemOut(BaseModel):
    company_id: str
    company_name: str
    blue_rate: float = 0.0
    blue_count: int = 0


class PackageAObservePortfolioDangerScoreItemOut(BaseModel):
    company_id: str
    company_name: str
    danger_score: int = 0
    blue_count: int = 0
    prev_day_incomplete_count: int = 0


class PackageAObservePortfolioPrevDayIncompleteItemOut(BaseModel):
    company_id: str
    company_name: str
    prev_day_incomplete_count: int = 0


class PackageAObservePortfolioAfterCutoffItemOut(BaseModel):
    company_id: str
    company_name: str
    after_cutoff_count: int = 0


class PackageAObservePortfolioStaleUpdateItemOut(BaseModel):
    company_id: str
    company_name: str
    last_activity_at: Optional[str] = None
    stale_days: Optional[int] = None


class PackageAObservePortfolioObservationOut(BaseModel):
    top_danger_score: List[PackageAObservePortfolioDangerScoreItemOut] = []
    top_prev_day_incomplete: List[PackageAObservePortfolioPrevDayIncompleteItemOut] = []
    top_after_cutoff: List[PackageAObservePortfolioAfterCutoffItemOut] = []
    top_blue_rate: List[PackageAObservePortfolioBlueRateItemOut] = []
    stale_updates: List[PackageAObservePortfolioStaleUpdateItemOut] = []


class PackageAObservePortfolioOut(BaseModel):
    companies: List[PackageAObservePortfolioCompanyOut]
    totals: PackageAObservePortfolioTotalsOut
    observation: PackageAObservePortfolioObservationOut
    generated_at: str


class WorkingCalendarExceptionOut(BaseModel):
    id: int
    target_date: str
    is_working_day: bool


class WorkingCalendarDayOut(BaseModel):
    date: str
    weekday: int
    is_working_day: bool
    source: Literal["exception", "weekday", "fallback"]


class WorkingCalendarMonthOut(BaseModel):
    company_id: str
    month: str
    default_working_weekdays: List[int]
    exceptions: List[WorkingCalendarExceptionOut]
    days: List[WorkingCalendarDayOut]


class WorkingCalendarExceptionIn(BaseModel):
    target_date: str = Field(..., description="YYYY-MM-DD")
    is_working_day: bool


class WorkingDaysPatchIn(BaseModel):
    company_id: str
    default_working_weekdays: List[int] = Field(
        ...,
        min_length=1,
        description="ISO 曜日 1=月 … 7=日",
    )
    exceptions: List[WorkingCalendarExceptionIn] = Field(default_factory=list)


class WorkingDaysPatchOut(BaseModel):
    ok: bool = True
    company_id: str
    default_working_weekdays: List[int]
    exception_count: int


# ─── 月報（sr/monthly）────────────────────────────────────────
class MonthlyReportCountRowOut(BaseModel):
    label: str
    count: int


class MonthlyReportAnomalyBreakdownRowOut(BaseModel):
    key: str
    label: str
    count: int


class MonthlyReportAuditBreakdownRowOut(BaseModel):
    key: str
    label: str
    count: int


class MonthlyReportMetricsOut(BaseModel):
    total_work_count: int = 0
    completed_count: int = 0
    planned_registered_count: int = 0
    actual_registered_count: int = 0
    started_without_planned_count: int = 0
    incomplete_count: int = 0
    article7_count: int = 0
    after_cutoff_count: int = 0
    anomaly_count: int = 0
    anomaly_breakdown: List[MonthlyReportAnomalyBreakdownRowOut] = Field(
        default_factory=list
    )
    anomaly_breakdown_note: str = ""
    audit_target_count: int = 0
    audit_response_rate: float = 0.0
    audit_breakdown: List[MonthlyReportAuditBreakdownRowOut] = Field(
        default_factory=list
    )
    audit_breakdown_note: str = ""
    by_process: List[MonthlyReportCountRowOut] = Field(default_factory=list)
    by_leader: List[MonthlyReportCountRowOut] = Field(default_factory=list)
    field_classification_breakdown: FieldClassificationBreakdownOut = Field(
        default_factory=FieldClassificationBreakdownOut
    )


class MonthlyReportAggregateOut(BaseModel):
    company_id: str
    company_name: str
    target_month: str
    target_month_label: str
    metrics: MonthlyReportMetricsOut
    previous_metrics: Optional[MonthlyReportMetricsOut] = None
    generated_summary: str
    consultant_comment: str = ""
    saved_report_id: Optional[int] = None
    saved_at: Optional[str] = None


class MonthlyReportSaveIn(BaseModel):
    company_id: str
    target_month: str = Field(..., description="YYYY-MM")
    generated_summary: str = ""
    consultant_comment: str = ""


class MonthlyReportSaveOut(BaseModel):
    id: int
    company_id: str
    target_month: str
    generated_summary: str
    consultant_comment: str = ""
    created_at: str
