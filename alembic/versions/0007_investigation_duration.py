"""Store investigation wall-clock duration for query history.

Revision ID: 0007_investigation_duration
Revises: 0006_investigation_input_method
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0007_investigation_duration"
down_revision: Union[str, None] = "0006_investigation_input_method"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "investigation_runs",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investigation_runs", "duration_ms")
