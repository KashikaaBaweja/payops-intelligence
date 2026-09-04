from datetime import datetime, timedelta

from payops_core.data.models import (
    ErrorCode,
    Merchant,
    Order,
    Payment,
    PaymentMethod,
    WebhookEvent,
)
from payops_core.models.schemas import TimeWindow
from sqlalchemy.orm import Session

WEBHOOK_WINDOW = TimeWindow(
    start=datetime(2024, 6, 18, 14, 0, 0),
    end=datetime(2024, 6, 18, 16, 0, 0),
)


def load_known_webhook_dataset(session: Session) -> None:
    """Payments with one normal, delayed, failed, missing, retry, duplicate, and mismatch case."""

    catalog_at = datetime(2024, 1, 1)
    session.add(
        PaymentMethod(
            method_id="card",
            name="Card",
            category="card",
            is_active=1,
            created_at=catalog_at,
            extra={"synthetic": True},
        )
    )
    session.add(
        ErrorCode(
            code="DO_NOT_HONOR",
            category="issuer",
            description="Issuer decline",
            retryable=0,
            created_at=catalog_at,
            extra={"synthetic": True},
        )
    )
    session.add(
        Merchant(
            merchant_id="M201",
            name="Cedar Digital Goods",
            country="US",
            status="active",
            mcc="5815",
            created_at=catalog_at,
            updated_at=catalog_at,
            extra={"synthetic": True},
        )
    )

    base = datetime(2024, 6, 18, 14, 10, 0)

    def add_payment(suffix: str, minutes: int, status: str = "succeeded") -> str:
        created = base + timedelta(minutes=minutes)
        payment_id = f"PWH{suffix}"
        session.add(
            Order(
                order_id=f"OWH{suffix}",
                merchant_id="M201",
                amount_cents=8900,
                currency="INR",
                status="paid" if status == "succeeded" else "created",
                created_at=created,
                updated_at=created,
                extra={"synthetic": True},
            )
        )
        session.add(
            Payment(
                payment_id=payment_id,
                order_id=f"OWH{suffix}",
                merchant_id="M201",
                method_id="card",
                amount_cents=8900,
                currency="INR",
                status=status,
                error_code=None if status == "succeeded" else "DO_NOT_HONOR",
                created_at=created,
                captured_at=created if status == "succeeded" else None,
                extra={"synthetic": True},
            )
        )
        session.flush()
        return payment_id

    def add_event(
        event_id: str,
        payment_id: str,
        status: str,
        delay_ms: int,
        event_type: str = "payment.succeeded",
        attempt: int = 1,
        key: str | None = None,
        offset_seconds: int = 0,
    ) -> None:
        payment = session.get(Payment, payment_id)
        created = payment.created_at + timedelta(seconds=offset_seconds)
        delivered = created + timedelta(milliseconds=delay_ms) if status != "failed" else None
        session.add(
            WebhookEvent(
                event_id=event_id,
                payment_id=payment_id,
                event_type=event_type,
                delivery_status=status,
                delay_ms=delay_ms,
                created_at=created,
                delivered_at=delivered,
                extra={
                    "synthetic": True,
                    "attempt": attempt,
                    "idempotency_key": key,
                },
            )
        )

    add_payment("001", 0)
    add_event("EWH001", "PWH001", "delivered", 90, key="ok-001")

    add_payment("002", 2)
    add_event("EWH002", "PWH002", "delayed", 60_000, key="late-002")

    add_payment("003", 4)
    add_event("EWH003", "PWH003", "failed", 0, key="fail-003")

    add_payment("004", 6)  # missing webhook

    add_payment("005", 8)
    add_event("EWH005A", "PWH005", "failed", 0, attempt=1, key="retry-005-a")
    add_event(
        "EWH005B",
        "PWH005",
        "delivered",
        120,
        attempt=2,
        key="retry-005-b",
        offset_seconds=8,
    )

    add_payment("006", 10)
    add_event("EWH006A", "PWH006", "delivered", 80, attempt=1, key="dup-006")
    add_event(
        "EWH006B",
        "PWH006",
        "delivered",
        95,
        attempt=1,
        key="dup-006",
        offset_seconds=3,
    )

    add_payment("007", 12)
    add_event(
        "EWH007",
        "PWH007",
        "delivered",
        100,
        event_type="payment.failed",
        key="mismatch-007",
    )
