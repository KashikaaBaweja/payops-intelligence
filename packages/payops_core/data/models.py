from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from payops_core.data.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    method_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    payments: Mapped[list["Payment"]] = relationship(back_populates="method")


class ErrorCode(Base):
    __tablename__ = "error_codes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    payments: Mapped[list["Payment"]] = relationship(back_populates="error")


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'inactive')",
            name="ck_merchants_status",
        ),
        Index("ix_merchants_status", "status"),
        Index("ix_merchants_country", "country"),
    )

    merchant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    mcc: Mapped[str] = mapped_column(String(8), nullable=False, default="5999")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    orders: Mapped[list["Order"]] = relationship(back_populates="merchant")
    payments: Mapped[list["Payment"]] = relationship(back_populates="merchant")
    settlements: Mapped[list["Settlement"]] = relationship(back_populates="merchant")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'paid', 'cancelled', 'partially_refunded', 'refunded')",
            name="ck_orders_status",
        ),
        CheckConstraint("amount_cents > 0", name="ck_orders_amount_positive"),
        Index("ix_orders_merchant_created", "merchant_id", "created_at"),
        Index("ix_orders_status", "status"),
    )

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    merchant: Mapped[Merchant] = relationship(back_populates="orders")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'cancelled')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        CheckConstraint(
            "(status <> 'failed') OR (error_code IS NOT NULL)",
            name="ck_payments_failed_has_error",
        ),
        Index("ix_payments_merchant_created", "merchant_id", "created_at"),
        Index("ix_payments_method_status", "method_id", "status"),
        Index("ix_payments_status_created", "status", "created_at"),
        Index("ix_payments_error_code", "error_code"),
        Index("ix_payments_order_id", "order_id"),
    )

    payment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False
    )
    merchant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False
    )
    method_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("payment_methods.method_id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("error_codes.code", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    order: Mapped[Order] = relationship(back_populates="payments")
    merchant: Mapped[Merchant] = relationship(back_populates="payments")
    method: Mapped[PaymentMethod] = relationship(back_populates="payments")
    error: Mapped[ErrorCode | None] = relationship(back_populates="payments")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="payment")
    webhook_events: Mapped[list["WebhookEvent"]] = relationship(back_populates="payment")


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'processed', 'failed')",
            name="ck_refunds_status",
        ),
        CheckConstraint("amount_cents > 0", name="ck_refunds_amount_positive"),
        Index("ix_refunds_payment_id", "payment_id"),
        Index("ix_refunds_status_created", "status", "created_at"),
    )

    refund_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("payments.payment_id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    payment: Mapped[Payment] = relationship(back_populates="refunds")


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'settled', 'failed')",
            name="ck_settlements_status",
        ),
        CheckConstraint("amount_cents > 0", name="ck_settlements_amount_positive"),
        Index("ix_settlements_merchant_created", "merchant_id", "created_at"),
        Index("ix_settlements_status", "status"),
    )

    settlement_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    merchant: Mapped[Merchant] = relationship(back_populates="settlements")


class Dispute(Base):
    __tablename__ = "disputes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'won', 'lost', 'closed')",
            name="ck_disputes_status",
        ),
        Index("ix_disputes_payment_id", "payment_id"),
        Index("ix_disputes_status_created", "status", "created_at"),
    )

    dispute_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("payments.payment_id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    payment: Mapped[Payment] = relationship(back_populates="disputes")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'delayed', 'failed')",
            name="ck_webhooks_delivery_status",
        ),
        CheckConstraint("delay_ms >= 0", name="ck_webhooks_delay_nonnegative"),
        Index("ix_webhooks_payment_id", "payment_id"),
        Index("ix_webhooks_status_created", "delivery_status", "created_at"),
        Index("ix_webhooks_event_type", "event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("payments.payment_id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False)
    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    payment: Mapped[Payment] = relationship(back_populates="webhook_events")
