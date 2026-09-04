"""Initial payment-operations schema.

Revision ID: 0001_payment_ops
Revises:
Create Date: 2024-06-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001_payment_ops"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("method_id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_table(
        "error_codes",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("retryable", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_table(
        "merchants",
        sa.Column("merchant_id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mcc", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'inactive')", name="ck_merchants_status"
        ),
    )
    op.create_index("ix_merchants_status", "merchants", ["status"])
    op.create_index("ix_merchants_country", "merchants", ["country"])

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "merchant_id",
            sa.String(length=32),
            sa.ForeignKey("merchants.merchant_id"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'paid', 'cancelled', 'partially_refunded', 'refunded')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_orders_amount_positive"),
    )
    op.create_index("ix_orders_merchant_created", "orders", ["merchant_id", "created_at"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "payments",
        sa.Column("payment_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "order_id", sa.String(length=32), sa.ForeignKey("orders.order_id"), nullable=False
        ),
        sa.Column(
            "merchant_id",
            sa.String(length=32),
            sa.ForeignKey("merchants.merchant_id"),
            nullable=False,
        ),
        sa.Column(
            "method_id",
            sa.String(length=32),
            sa.ForeignKey("payment_methods.method_id"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "error_code", sa.String(length=64), sa.ForeignKey("error_codes.code"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'cancelled')",
            name="ck_payments_status",
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "(status <> 'failed') OR (error_code IS NOT NULL)",
            name="ck_payments_failed_has_error",
        ),
    )
    op.create_index("ix_payments_merchant_created", "payments", ["merchant_id", "created_at"])
    op.create_index("ix_payments_method_status", "payments", ["method_id", "status"])
    op.create_index("ix_payments_status_created", "payments", ["status", "created_at"])
    op.create_index("ix_payments_error_code", "payments", ["error_code"])
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_created_at", "payments", ["created_at"])

    op.create_table(
        "refunds",
        sa.Column("refund_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "payment_id", sa.String(length=32), sa.ForeignKey("payments.payment_id"), nullable=False
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested', 'processed', 'failed')", name="ck_refunds_status"
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_refunds_amount_positive"),
    )
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])
    op.create_index("ix_refunds_status_created", "refunds", ["status", "created_at"])

    op.create_table(
        "settlements",
        sa.Column("settlement_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "merchant_id",
            sa.String(length=32),
            sa.ForeignKey("merchants.merchant_id"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'settled', 'failed')", name="ck_settlements_status"
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_settlements_amount_positive"),
    )
    op.create_index("ix_settlements_merchant_created", "settlements", ["merchant_id", "created_at"])
    op.create_index("ix_settlements_status", "settlements", ["status"])

    op.create_table(
        "disputes",
        sa.Column("dispute_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "payment_id", sa.String(length=32), sa.ForeignKey("payments.payment_id"), nullable=False
        ),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'won', 'lost', 'closed')", name="ck_disputes_status"
        ),
    )
    op.create_index("ix_disputes_payment_id", "disputes", ["payment_id"])
    op.create_index("ix_disputes_status_created", "disputes", ["status", "created_at"])

    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "payment_id", sa.String(length=32), sa.ForeignKey("payments.payment_id"), nullable=False
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("delivery_status", sa.String(length=16), nullable=False),
        sa.Column("delay_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'delayed', 'failed')",
            name="ck_webhooks_delivery_status",
        ),
        sa.CheckConstraint("delay_ms >= 0", name="ck_webhooks_delay_nonnegative"),
    )
    op.create_index("ix_webhooks_payment_id", "webhook_events", ["payment_id"])
    op.create_index(
        "ix_webhooks_status_created", "webhook_events", ["delivery_status", "created_at"]
    )
    op.create_index("ix_webhooks_event_type", "webhook_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("disputes")
    op.drop_table("settlements")
    op.drop_table("refunds")
    op.drop_table("payments")
    op.drop_table("orders")
    op.drop_table("merchants")
    op.drop_table("error_codes")
    op.drop_table("payment_methods")
