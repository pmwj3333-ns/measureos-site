"""working_calendar + default_working_weekdays

Revision ID: 20260519100004
Revises: 20260519100003
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100004"
down_revision: Union[str, None] = "20260519100003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("company_settings") as batch_op:
        batch_op.add_column(
            sa.Column("default_working_weekdays", sa.String(), nullable=True)
        )
    op.create_table(
        "working_calendar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("is_working_day", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "target_date", name="uq_working_calendar_company_date"
        ),
    )
    op.create_index(
        "ix_working_calendar_company_id",
        "working_calendar",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_working_calendar_company_id", table_name="working_calendar")
    op.drop_table("working_calendar")
    with op.batch_alter_table("company_settings") as batch_op:
        batch_op.drop_column("default_working_weekdays")
