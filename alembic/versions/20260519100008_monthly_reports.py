"""monthly_reports テーブル追加。"""

from alembic import op
import sqlalchemy as sa


revision = "20260519100008"
down_revision = "20260519100007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("target_month", sa.String(), nullable=False),
        sa.Column("generated_summary", sa.String(), nullable=False, server_default=""),
        sa.Column("consultant_comment", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "target_month",
            name="uq_monthly_reports_company_month",
        ),
    )
    op.create_index(
        "ix_monthly_reports_company_id",
        "monthly_reports",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_monthly_reports_company_id", table_name="monthly_reports")
    op.drop_table("monthly_reports")
