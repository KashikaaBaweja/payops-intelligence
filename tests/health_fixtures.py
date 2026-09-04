from datetime import datetime

from payops_core.data.models import (
    Dispute,
    ErrorCode,
    Merchant,
    Order,
    Payment,
    PaymentMethod,
    Refund,
    WebhookEvent,
)
from sqlalchemy.orm import Session

from tests.analytics_fixtures import CURRENT_WINDOW

HEALTH_WINDOW = CURRENT_WINDOW


def load_health_dataset(session: Session) -> None:
    """Three merchants with known healthy, degraded, and critical profiles."""

    catalog_at = datetime(2024, 1, 1)
    for method_id, name, category in (("card", "Card", "card"), ("upi", "UPI", "realtime")):
        session.add(
            PaymentMethod(
                method_id=method_id,
                name=name,
                category=category,
                is_active=1,
                created_at=catalog_at,
                extra={"synthetic": True},
            )
        )
    session.add(
        ErrorCode(
            code="GATEWAY_TIMEOUT",
            category="gateway",
            description="Processor timeout",
            retryable=1,
            created_at=catalog_at,
            extra={"synthetic": True},
        )
    )
    session.add(
        ErrorCode(
            code="INSUFFICIENT_FUNDS",
            category="issuer",
            description="Issuer decline",
            retryable=0,
            created_at=catalog_at,
            extra={"synthetic": True},
        )
    )
    for merchant_id, name in (
        ("M801", "Healthy Goods"),
        ("M802", "Degraded Goods"),
        ("M803", "Critical Goods"),
    ):
        session.add(
            Merchant(
                merchant_id=merchant_id,
                name=name,
                country="IN",
                status="active",
                mcc="5999",
                created_at=catalog_at,
                updated_at=catalog_at,
                extra={"synthetic": True},
            )
        )

    seq = 0

    def add_payment(
        merchant_id: str,
        created_at: datetime,
        status: str,
        error_code: str | None = None,
        webhook_status: str = "delivered",
        refund: bool = False,
        dispute: bool = False,
        method_id: str = "card",
    ) -> None:
        nonlocal seq
        seq += 1
        order_id = f"H{seq:03d}"
        payment_id = f"HP{seq:03d}"
        session.add(
            Order(
                order_id=order_id,
                merchant_id=merchant_id,
                amount_cents=1000,
                currency="INR",
                status="paid" if status == "succeeded" else "created",
                created_at=created_at,
                updated_at=created_at,
                extra={"synthetic": True},
            )
        )
        session.add(
            Payment(
                payment_id=payment_id,
                order_id=order_id,
                merchant_id=merchant_id,
                method_id=method_id,
                amount_cents=1000,
                currency="INR",
                status=status,
                error_code=error_code,
                created_at=created_at,
                captured_at=created_at if status == "succeeded" else None,
                extra={"synthetic": True},
            )
        )
        session.add(
            WebhookEvent(
                event_id=f"HE{seq:03d}",
                payment_id=payment_id,
                event_type=f"payment.{status}",
                delivery_status=webhook_status,
                delay_ms=80 if webhook_status == "delivered" else 0,
                created_at=created_at,
                delivered_at=created_at if webhook_status == "delivered" else None,
                extra={"synthetic": True},
            )
        )
        if refund:
            session.add(
                Refund(
                    refund_id=f"HR{seq:03d}",
                    payment_id=payment_id,
                    amount_cents=500,
                    status="processed",
                    created_at=created_at,
                    extra={"synthetic": True},
                )
            )
        if dispute:
            session.add(
                Dispute(
                    dispute_id=f"HD{seq:03d}",
                    payment_id=payment_id,
                    reason="fraud",
                    status="open",
                    created_at=created_at,
                    extra={"synthetic": True},
                )
            )

    for index in range(20):
        add_payment("M801", datetime(2024, 6, 15, 10, 5 + index), "succeeded")
    for index in range(10):
        add_payment("M801", datetime(2024, 6, 15, 8, 10 + index), "succeeded")

    for index in range(17):
        add_payment(
            "M802",
            datetime(2024, 6, 15, 10, 5 + index),
            "succeeded",
            refund=index < 2,
        )
    for index in range(3):
        add_payment(
            "M802",
            datetime(2024, 6, 15, 11, 10 + index),
            "failed",
            error_code="GATEWAY_TIMEOUT",
            webhook_status="failed",
            method_id="upi",
        )
    for index in range(9):
        add_payment("M802", datetime(2024, 6, 15, 8, 10 + index), "succeeded")
    add_payment(
        "M802",
        datetime(2024, 6, 15, 8, 50),
        "failed",
        error_code="INSUFFICIENT_FUNDS",
    )

    for index in range(3):
        add_payment(
            "M803",
            datetime(2024, 6, 15, 10, 5 + index),
            "succeeded",
            refund=True,
            dispute=index < 2,
        )
    for index in range(7):
        add_payment(
            "M803",
            datetime(2024, 6, 15, 11, 5 + index),
            "failed",
            error_code="GATEWAY_TIMEOUT",
            webhook_status="failed",
            method_id="upi",
        )
    for index in range(10):
        add_payment("M803", datetime(2024, 6, 15, 8, 10 + index), "succeeded")
