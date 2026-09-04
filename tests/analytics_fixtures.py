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
from payops_core.models.schemas import TimeWindow
from sqlalchemy.orm import Session

CURRENT_WINDOW = TimeWindow(
    start=datetime(2024, 6, 15, 10, 0, 0),
    end=datetime(2024, 6, 15, 12, 0, 0),
)
PREVIOUS_WINDOW = TimeWindow(
    start=datetime(2024, 6, 15, 8, 0, 0),
    end=datetime(2024, 6, 15, 10, 0, 0),
)


def load_known_ops_dataset(session: Session) -> None:
    """Tiny fictional dataset with exact, asserted rates."""

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
    for code, category, description in (
        ("GATEWAY_TIMEOUT", "gateway", "Processor timeout"),
        ("INSUFFICIENT_FUNDS", "issuer", "Issuer decline"),
    ):
        session.add(
            ErrorCode(
                code=code,
                category=category,
                description=description,
                retryable=1,
                created_at=catalog_at,
                extra={"synthetic": True},
            )
        )
    for merchant_id, name in (("M102", "Harbor Retail"), ("M201", "Cedar Digital Goods")):
        session.add(
            Merchant(
                merchant_id=merchant_id,
                name=name,
                country="IN",
                status="active",
                mcc="5311",
                created_at=catalog_at,
                updated_at=catalog_at,
                extra={"synthetic": True},
            )
        )

    seq = 0

    def add_payment(
        merchant_id: str,
        method_id: str,
        created_at: datetime,
        status: str,
        error_code: str | None = None,
        webhook_status: str = "delivered",
        refund: bool = False,
        dispute: bool = False,
    ) -> None:
        nonlocal seq
        seq += 1
        order_id = f"O{seq:03d}"
        payment_id = f"P{seq:03d}"
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
                event_id=f"E{seq:03d}",
                payment_id=payment_id,
                event_type=f"payment.{status}",
                delivery_status=webhook_status,
                delay_ms=90 if webhook_status == "delivered" else 0,
                created_at=created_at,
                delivered_at=created_at if webhook_status == "delivered" else None,
                extra={"synthetic": True},
            )
        )
        if refund:
            session.add(
                Refund(
                    refund_id=f"R{seq:03d}",
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
                    dispute_id=f"D{seq:03d}",
                    payment_id=payment_id,
                    reason="fraud",
                    status="open",
                    created_at=created_at,
                    extra={"synthetic": True},
                )
            )

    # M102 current window: 8 UPI success, 2 UPI GATEWAY_TIMEOUT, 2 card success.
    for index in range(8):
        add_payment(
            "M102",
            "upi",
            datetime(2024, 6, 15, 10, 5 + index),
            "succeeded",
            refund=index < 2,
            dispute=index == 2,
        )
    for index in range(2):
        add_payment(
            "M102",
            "upi",
            datetime(2024, 6, 15, 11, 10 + index),
            "failed",
            error_code="GATEWAY_TIMEOUT",
            webhook_status="failed",
        )
    for index in range(2):
        add_payment("M102", "card", datetime(2024, 6, 15, 11, 40 + index), "succeeded")

    # M201 current window: 4 card success, 1 card failure.
    for index in range(4):
        add_payment("M201", "card", datetime(2024, 6, 15, 10, 20 + index), "succeeded")
    add_payment(
        "M201",
        "card",
        datetime(2024, 6, 15, 11, 0),
        "failed",
        error_code="INSUFFICIENT_FUNDS",
    )

    # M102 previous window: 5 UPI success.
    for index in range(5):
        add_payment("M102", "upi", datetime(2024, 6, 15, 8, 10 + index), "succeeded")
