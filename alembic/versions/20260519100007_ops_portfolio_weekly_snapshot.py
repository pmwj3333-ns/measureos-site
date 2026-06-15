"""ops_portfolio_weekly_snapshot

Revision ID: 20260519100007
Revises: 20260519100006
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100007"
down_revision: Union[str, None] = "20260519100006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ops_portfolio_weekly_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("blue_count", sa.Integer(), nullable=False),
        sa.Column("blue_rate", sa.Float(), nullable=False),
        sa.Column("danger_score", sa.Integer(), nullable=False),
        sa.Column("prev_day_incomplete_count", sa.Integer(), nullable=False),
        sa.Column("after_cutoff_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ops_portfolio_weekly_snapshot_company_id",
        "ops_portfolio_weekly_snapshot",
        ["company_id"],
    )
    op.create_index(
        "ix_ops_portfolio_weekly_snapshot_generated_at",
        "ops_portfolio_weekly_snapshot",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ops_portfolio_weekly_snapshot_generated_at",
        table_name="ops_portfolio_weekly_snapshot",
    )
    op.drop_index(
        "ix_ops_portfolio_weekly_snapshot_company_id",
        table_name="ops_portfolio_weekly_snapshot",
    )
    op.drop_table("ops_portfolio_weekly_snapshot")
