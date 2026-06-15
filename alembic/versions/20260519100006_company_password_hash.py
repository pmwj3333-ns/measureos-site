"""company_master.company_password_hash

Revision ID: 20260519100006
Revises: 20260519100005
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100006"
down_revision: Union[str, None] = "20260519100005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("company_master") as batch_op:
        batch_op.add_column(sa.Column("company_password_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("company_master") as batch_op:
        batch_op.drop_column("company_password_hash")
