from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, Time
from app.database import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    company_id         = Column(String, primary_key=True)
    company_name       = Column(String, default="")
    unit               = Column(String, default="個")
    tolerance_value    = Column(Integer, default=0)
    day_boundary_time  = Column(Time, nullable=True)
    work_end_time      = Column(Time, nullable=True)
    judgement_time     = Column(Time, nullable=True)
    field_users        = Column(String, nullable=True, default="")
    input_mode         = Column(String, nullable=True, default="manufacturing")


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
    created_at      = Column(DateTime, nullable=True)
    updated_at      = Column(DateTime, nullable=True)
    business_date_source = Column(String, nullable=True)
    business_date_debug_json = Column(String, nullable=True)

    planned_work_type = Column(String, nullable=True)
    planned_work_label = Column(String, nullable=True)
    planned_item_name = Column(String, nullable=True)
    planned_lines_json = Column(String, nullable=True)
    planned_value   = Column(Float, nullable=True)
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

    is_unregistered_user = Column(Boolean, default=False)
    user_source          = Column(String, nullable=True, default="master")
