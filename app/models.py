from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    Time,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from app.database import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    company_id         = Column(String, primary_key=True)
    # 表示用（company_id とは別。sr_v2 / 旧 settings 共通）
    company_name       = Column(String, nullable=True, default="")
    unit               = Column(String, default="個")
    # 予告と実績の差の許容（±）。None は未設定扱い（判定側は 0 相当に読み替え可）
    tolerance_value    = Column(Integer, nullable=True)
    day_boundary_time  = Column(Time, nullable=True)
    work_end_time      = Column(Time, nullable=True)
    judgement_time     = Column(Time, nullable=True)
    # 第7条・3条：受注がこの時刻以降なら製造スロット日を翌々営業日へ（未設定なら3条スキップ）
    order_cutoff_time  = Column(Time, nullable=True)
    field_users        = Column(String, nullable=True, default="")
    input_mode         = Column(String, nullable=True, default="manufacturing")
    # Package A-D（B以上でフェーズ2・赤系を有効化）
    package_code       = Column(String, nullable=False, default="A")
    # 互換用（package_code 優先。新規は package_code のみで判定）
    phase2_enabled     = Column(Boolean, nullable=True, default=False)


class CompanyCalendar(Base):
    __tablename__ = "company_calendar"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    company_id  = Column(String, nullable=False)
    date        = Column(Date, nullable=False)
    is_workday  = Column(Boolean, default=False)


class WorkUnit(Base):
    __tablename__ = "work_unit"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    company_id      = Column(String, nullable=False)
    task_id         = Column(String, nullable=False)
    process_id      = Column(String, nullable=False)
    user_id         = Column(String, nullable=False)
    business_date   = Column(Date, nullable=False)
    input_source    = Column(String, nullable=True)
    created_at      = Column(DateTime, nullable=True)
    updated_at      = Column(DateTime, nullable=True)
    business_date_source = Column(String, nullable=True)
    business_date_debug_json = Column(String, nullable=True)

    planned_work_type = Column(String, nullable=True)
    planned_work_label = Column(String, nullable=True)
    planned_item_name = Column(String, nullable=True)
    planned_lines_json = Column(String, nullable=True)
    planned_value   = Column(Float, nullable=True)
    planned_at      = Column(DateTime, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    actual_work_type = Column(String, nullable=True)
    actual_work_label = Column(String, nullable=True)
    actual_item_name = Column(String, nullable=True)
    actual_lines_json = Column(String, nullable=True)
    actual_value    = Column(Float, nullable=True)
    actual_at       = Column(DateTime, nullable=True)
    actual_memo     = Column(String, nullable=True)
    diff_value      = Column(Float, nullable=True)

    pattern_a       = Column(Boolean, nullable=True)
    pattern_b       = Column(Boolean, nullable=True)
    user_pattern    = Column(String, nullable=True)

    status          = Column(String, nullable=True, default="normal")
    system_pattern = Column(String, nullable=True)

    is_missing      = Column(Boolean, default=False)
    is_invalid_flow = Column(Boolean, default=False)
    is_diff_anomaly = Column(Boolean, default=False)
    anomaly_started_at = Column(DateTime, nullable=True)

    is_unregistered_user = Column(Boolean, default=False)
    user_source          = Column(String, nullable=True, default="master")

    # 第5条・Package A: 第7条（open）に無い商品の実績（数量・順序は対象外）
    is_deviation = Column(Boolean, nullable=True, default=False)
    is_article7_deviation = Column(Boolean, nullable=True, default=False)
    deviation_reason = Column(String, nullable=True)

    # 事務の反映判断（異常判定・status とは独立。append-only のまま履歴として残す）
    reflection_status = Column(String, nullable=False, default="pending")
    reflection_reject_reason_code = Column(String, nullable=True)
    reflection_reject_reason_detail = Column(String, nullable=True)


class ProductMaster(Base):
    """第5条・商品マスタ（会社単位）。現場は商品名で入力し、裏で product_code を紐づけ可能。"""

    __tablename__ = "product_master"
    __table_args__ = (
        Index("ix_product_master_company_id", "company_id"),
        UniqueConstraint("company_id", "label", name="uq_product_master_company_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String, nullable=False)
    product_code = Column(String, nullable=True)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class PriorityItem(Base):
    """第7条フェーズ1: 事務（OS）が決める優先指示（work_unit 非依存）。現場の「やり方」は持たない。"""

    __tablename__ = "priority_item"
    __table_args__ = (Index("ix_priority_item_company_id", "company_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String, nullable=False)
    product_code = Column(String, nullable=False, default="")
    label = Column(String, nullable=False)
    ship_value = Column(Float, nullable=False)
    stock_qty = Column(Float, nullable=False, default=0)
    prod_value = Column(Float, nullable=False)
    # 旧スキーマ互換: かつての単一数量列。INSERT 時は ship_value と同値を入れる（NOT NULL の DB 対策）
    value = Column(Float, nullable=True)
    due_date = Column(String, nullable=True)
    # open = 現場・一覧に出す / closed = 事務クローズ済み（一覧・GET items では返さない）
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class StockItem(Base):
    """第7条ステップ①: 在庫CSV取り込み（計算なし・投入のみ）。"""

    __tablename__ = "stock_item"
    __table_args__ = (Index("ix_stock_item_company_id", "company_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String, nullable=False)
    product_code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    stock_qty = Column(Float, nullable=False)
    safety_stock = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=True)


class ShipmentPlanItem(Base):
    """第7条ステップ②: 出荷予定CSV取り込み（在庫突合・第7条計算は別途）。"""

    __tablename__ = "shipment_plan_item"
    __table_args__ = (Index("ix_shipment_plan_item_company_id", "company_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String, nullable=False)
    product_code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    ship_qty = Column(Float, nullable=False)
    due_date = Column(String, nullable=False)
    ordered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)


class WorkUnitStatusHistory(Base):
    """work_unit.status の変化履歴（挿入ロジックは別途）。"""

    __tablename__ = "work_unit_status_history"
    __table_args__ = (
        Index("ix_work_unit_status_history_work_unit_id", "work_unit_id"),
        Index("ix_work_unit_status_history_changed_at", "changed_at"),
        Index("ix_work_unit_status_history_unit_changed", "work_unit_id", "changed_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_unit_id = Column(Integer, ForeignKey("work_unit.id"), nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    changed_at = Column(DateTime, nullable=False)
    trigger_type = Column(String, nullable=True)


class OfficeClosedWorkUnitSuppress(Base):
    """事務が POST /work/{id}/close で1件閉じた元 head。レコードは残すが事務一覧（hide_office_closed_sources）では除外する。"""

    __tablename__ = "office_closed_work_unit_suppress"

    peer_unit_id = Column(Integer, ForeignKey("work_unit.id"), primary_key=True)
    created_at = Column(DateTime, nullable=True)
