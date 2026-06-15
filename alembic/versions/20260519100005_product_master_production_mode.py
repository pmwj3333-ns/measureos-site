"""product_master.production_mode

Revision ID: 20260519100005
Revises: 20260519100004
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100005"
down_revision: Union[str, None] = "20260519100004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("product_master") as batch_op:
        batch_op.add_column(
            sa.Column(
                "production_mode",
                sa.String(),
                nullable=False,
                server_default="manufacture",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("product_master") as batch_op:
        batch_op.drop_column("production_mode")
