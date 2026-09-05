"""Index investigation_runs.created_at for recent-list queries.

Revision ID: 0005_investigation_created_index
Revises: 0004_ledger_accounts
Create Date: 2024-06-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005_investigation_created_index"
down_revision: Union[str, None] = "0004_ledger_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_investigation_runs_created_at",
        "investigation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigation_runs_created_at", table_name="investigation_runs")
