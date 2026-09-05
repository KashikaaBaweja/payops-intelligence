"""Add document_chunks for RAG / pgvector storage.

Revision ID: 0002_document_chunks
Revises: 0001_payment_ops
Create Date: 2024-06-16
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002_document_chunks"
down_revision: Union[str, None] = "0001_payment_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        vector_available = bind.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        ).scalar()
        if vector_available:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            op.execute(
                """
                CREATE TABLE document_chunks (
                    chunk_id VARCHAR(64) PRIMARY KEY,
                    document_id VARCHAR(64) NOT NULL,
                    source TEXT NOT NULL,
                    section TEXT NOT NULL,
                    body TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    embedding vector(128) NOT NULL
                )
                """
            )
            op.execute(
                "CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id)"
            )
            return
    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_table("document_chunks")
