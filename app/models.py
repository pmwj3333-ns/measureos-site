from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, Time, ForeignKey, Index
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
    field_users        = Column(String, nullable=True, default="")
    input_mode         = Column(String, nullable=True, default="manufacturing")
    # True: blue→red 昇格・judgement_red_deadline_at を有効（フェーズ2）
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
