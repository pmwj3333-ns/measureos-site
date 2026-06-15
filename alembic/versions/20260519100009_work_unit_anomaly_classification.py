"""work_unit.anomaly_classification_json（第5条中分類）"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519100009"
down_revision: Union[str, None] = "20260519100008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("work_unit") as batch_op:
        batch_op.add_column(
            sa.Column("anomaly_classification_json", sa.String(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("work_unit") as batch_op:
        batch_op.drop_column("anomaly_classification_json")
