"""product_master.safety_stock_value

Revision ID: 20260519100002
Revises: 20260519000001
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100002"
down_revision: Union[str, None] = "20260519000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("product_master") as batch_op:
        batch_op.add_column(sa.Column("safety_stock_value", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("product_master") as batch_op:
        batch_op.drop_column("safety_stock_value")
