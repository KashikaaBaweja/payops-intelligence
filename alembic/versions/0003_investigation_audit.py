"""Persist investigation reports, traces, and evidence citations.

Revision ID: 0003_investigation_audit
Revises: 0002_document_chunks
Create Date: 2024-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_investigation_audit"
down_revision: Union[str, None] = "0002_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_runs",
        sa.Column("investigation_id", sa.String(length=64), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("merchant_id", sa.String(length=32), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("trace_json", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "evidence_index",
        sa.Column("evidence_id", sa.String(length=128), primary_key=True),
        sa.Column("investigation_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_evidence_index_investigation",
        "evidence_index",
        ["investigation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_index_investigation", table_name="evidence_index")
    op.drop_table("evidence_index")
    op.drop_table("investigation_runs")
