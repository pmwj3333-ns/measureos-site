"""priority_item.is_after_cutoff（第3条 Package A 観測）

Revision ID: 20260519100003
Revises: 20260519100002
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100003"
down_revision: Union[str, None] = "20260519100002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("priority_item") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_after_cutoff",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("priority_item") as batch_op:
        batch_op.drop_column("is_after_cutoff")
