"""Live ledger accounts, transfers, entries, and audit events.

Revision ID: 0004_ledger_accounts
Revises: 0003_investigation_audit
Create Date: 2024-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_ledger_accounts"
down_revision: Union[str, None] = "0003_investigation_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        sa.Column("account_id", sa.String(length=32), primary_key=True),
        sa.Column("merchant_id", sa.String(length=32), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("balance_cents", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("balance_cents >= 0", name="ck_ledger_accounts_balance_nonnegative"),
        sa.CheckConstraint(
            "kind IN ('merchant_wallet', 'platform_clearing')",
            name="ck_ledger_accounts_kind",
        ),
        sa.CheckConstraint("status IN ('active', 'frozen')", name="ck_ledger_accounts_status"),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.merchant_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_ledger_accounts_merchant", "ledger_accounts", ["merchant_id"])
    op.create_table(
        "ledger_transfers",
        sa.Column("transfer_id", sa.String(length=32), primary_key=True),
        sa.Column("from_account_id", sa.String(length=32), nullable=False),
        sa.Column("to_account_id", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("isolation_level", sa.String(length=32), nullable=False),
        sa.Column("fail_at", sa.String(length=32), nullable=True),
        sa.Column("failure_point", sa.String(length=64), nullable=True),
        sa.Column("before_from_cents", sa.Integer(), nullable=False),
        sa.Column("before_to_cents", sa.Integer(), nullable=False),
        sa.Column("after_from_cents", sa.Integer(), nullable=False),
        sa.Column("after_to_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_ledger_transfers_amount_positive"),
        sa.CheckConstraint(
            "status IN ('committed', 'rolled_back')",
            name="ck_ledger_transfers_status",
        ),
        sa.ForeignKeyConstraint(
            ["from_account_id"],
            ["ledger_accounts.account_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_account_id"],
            ["ledger_accounts.account_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_ledger_transfers_created", "ledger_transfers", ["created_at"])
    op.create_table(
        "ledger_entries",
        sa.Column("entry_id", sa.String(length=32), primary_key=True),
        sa.Column("transfer_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_ledger_entries_amount_positive"),
        sa.CheckConstraint(
            "direction IN ('debit', 'credit')",
            name="ck_ledger_entries_direction",
        ),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["ledger_transfers.transfer_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["ledger_accounts.account_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_ledger_entries_transfer", "ledger_entries", ["transfer_id"])
    op.create_table(
        "ledger_audit_events",
        sa.Column("audit_id", sa.String(length=32), primary_key=True),
        sa.Column("transfer_id", sa.String(length=32), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["ledger_transfers.transfer_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ledger_audit_transfer", "ledger_audit_events", ["transfer_id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_audit_transfer", table_name="ledger_audit_events")
    op.drop_table("ledger_audit_events")
    op.drop_index("ix_ledger_entries_transfer", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_ledger_transfers_created", table_name="ledger_transfers")
    op.drop_table("ledger_transfers")
    op.drop_index("ix_ledger_accounts_merchant", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
