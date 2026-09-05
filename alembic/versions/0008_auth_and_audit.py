"""Operator accounts, sessions, password resets, and security audit.

Revision ID: 0008_auth_and_audit
Revises: 0007_investigation_duration
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008_auth_and_audit"
down_revision: Union[str, None] = "0007_investigation_duration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_auth_users_role"),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_auth_users_status"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_auth_users_email", "auth_users", ["email"], unique=True)
    op.create_index("ix_auth_users_role_status", "auth_users", ["role", "status"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=240), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user", "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "password_reset_tokens",
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index(
        "ix_password_reset_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["created_at"], unique=False)
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_type", "audit_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_type", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_password_reset_token_hash", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_auth_sessions_user", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_auth_users_role_status", table_name="auth_users")
    op.drop_index("ix_auth_users_email", table_name="auth_users")
    op.drop_table("auth_users")
