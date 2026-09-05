"""Record whether an investigation query originated from text or voice.

Revision ID: 0006_investigation_input_method
Revises: 0005_investigation_created_index
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006_investigation_input_method"
down_revision: Union[str, None] = "0005_investigation_created_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "investigation_runs",
        sa.Column("input_method", sa.String(length=8), nullable=False, server_default="text"),
    )


def downgrade() -> None:
    op.drop_column("investigation_runs", "input_method")
