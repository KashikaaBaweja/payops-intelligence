"""Seedable fictional payments universe. Contains no real customer data."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from payops_core.data.models import (
    Dispute,
    ErrorCode,
    LedgerAccount,
    LedgerAuditEvent,
    LedgerEntry,
    LedgerTransfer,
    Merchant,
    Order,
    Payment,
    PaymentMethod,
    Refund,
    Settlement,
    WebhookEvent,
)
from payops_core.ledger.accounts import seed_ledger_accounts

METHODS = [
    ("card", "Card", "card"),
    ("upi", "UPI", "realtime"),
    ("netbanking", "Netbanking", "bank"),
    ("wallet", "Wallet", "wallet"),
]

ERROR_CODES = [
    ("GATEWAY_TIMEOUT", "gateway", "Method processor did not respond in time.", 1),
    ("INSUFFICIENT_FUNDS", "issuer", "Issuer declined for insufficient funds.", 0),
    ("DO_NOT_HONOR", "issuer", "Generic issuer decline.", 0),
    ("AUTHENTICATION_FAILED", "customer", "3DS or UPI PIN authentication failed.", 1),
    ("WEBHOOK_TIMEOUT", "platform", "Webhook consumer did not acknowledge in time.", 1),
]

MERCHANTS = [
    ("M101", "Northwind Checkout", "IN", "5999"),
    ("M102", "Harbor Retail", "IN", "5311"),
    ("M201", "Cedar Digital Goods", "US", "5815"),
    ("M305", "Low-volume Labs", "SG", "7372"),
    ("M410", "Summit Subscriptions", "GB", "5968"),
]

INCIDENT_UPI_SPIKE = {
    "incident_id": "INC-UPI-M102",
    "merchant_id": "M102",
    "method_id": "upi",
    "start": datetime(2024, 6, 15, 10, 0, 0),
    "end": datetime(2024, 6, 15, 12, 0, 0),
    "cause": "UPI gateway timeouts at the method processor",
}
INCIDENT_WEBHOOK_DELAY = {
    "incident_id": "INC-WH-M201",
    "merchant_id": "M201",
    "start": datetime(2024, 6, 18, 14, 0, 0),
    "end": datetime(2024, 6, 18, 16, 0, 0),
    "cause": "Webhook delivery delays after successful capture",
}
INCIDENT_SPARSE = {
    "incident_id": "INC-SPARSE-M305",
    "merchant_id": "M305",
    "start": datetime(2024, 5, 1, 0, 0, 0),
    "end": datetime(2024, 5, 2, 0, 0, 0),
    "cause": "Insufficient volume by design",
}

PLANTED_INCIDENTS = [INCIDENT_UPI_SPIKE, INCIDENT_WEBHOOK_DELAY, INCIDENT_SPARSE]


def generate(session: Session, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    _reset(session)
    _catalog(session)
    seed_ledger_accounts(session)
    payment_count = _traffic(session, rng)
    payment_count = _plant_incidents(session, rng, payment_count)
    _settlements(session)
    session.flush()
    return {
        "payments": payment_count,
        "merchants": len(MERCHANTS),
        "incidents": PLANTED_INCIDENTS,
    }


def _reset(session: Session) -> None:
    models = (
        LedgerAuditEvent,
        LedgerEntry,
        LedgerTransfer,
        LedgerAccount,
        WebhookEvent,
        Dispute,
        Refund,
        Settlement,
        Payment,
        Order,
        ErrorCode,
        PaymentMethod,
        Merchant,
    )
    for model in models:
        session.query(model).delete()


def _catalog(session: Session) -> None:
    created = datetime(2024, 1, 1, 0, 0, 0)
    for method_id, name, category in METHODS:
        session.add(
            PaymentMethod(
                method_id=method_id,
                name=name,
                category=category,
                is_active=1,
                created_at=created,
                extra={"synthetic": True},
            )
        )
    for code, category, description, retryable in ERROR_CODES:
        session.add(
            ErrorCode(
                code=code,
                category=category,
                description=description,
                retryable=retryable,
                created_at=created,
                extra={"synthetic": True},
            )
        )
    for merchant_id, name, country, mcc in MERCHANTS:
        session.add(
            Merchant(
                merchant_id=merchant_id,
                name=name,
                country=country,
                status="active",
                mcc=mcc,
                created_at=created,
                updated_at=created,
                extra={"risk_tier": "standard", "synthetic": True},
            )
        )


def _traffic(session: Session, rng: random.Random) -> int:
    base = datetime(2024, 6, 1, 0, 0, 0)
    payment_count = 0
    for day in range(30):
        for merchant_id, *_ in MERCHANTS:
            volume = 8 if merchant_id == "M305" else 22
            for _ in range(volume):
                created = base + timedelta(days=day, minutes=rng.randint(0, 24 * 60 - 1))
                method_id = rng.choice(["card", "upi", "netbanking", "wallet"])
                amount = rng.randint(500, 25000)
                status, error_code, delay_ms = _outcome(rng, merchant_id, method_id, created)
                payment_count = _insert_payment(
                    session,
                    payment_count,
                    merchant_id,
                    method_id,
                    created,
                    amount,
                    status,
                    error_code,
                    delay_ms,
                    "delayed" if delay_ms >= 30_000 else "delivered",
                    rng,
                )
    return payment_count


def _plant_incidents(session: Session, rng: random.Random, payment_count: int) -> int:
    start = INCIDENT_UPI_SPIKE["start"]
    for minute in range(0, 120, 3):
        created = start + timedelta(minutes=minute)
        failed = minute % 5 != 0
        payment_count = _insert_payment(
            session,
            payment_count,
            "M102",
            "upi",
            created,
            15000,
            "failed" if failed else "succeeded",
            "GATEWAY_TIMEOUT" if failed else None,
            rng.randint(80, 2000),
            "delivered",
            rng,
        )

    start = INCIDENT_WEBHOOK_DELAY["start"]
    for minute in range(0, 120, 4):
        created = start + timedelta(minutes=minute)
        payment_count = _insert_payment(
            session,
            payment_count,
            "M201",
            "card",
            created,
            8900,
            "succeeded",
            None,
            rng.randint(45_000, 180_000),
            "delayed",
            rng,
        )
    return payment_count


def _insert_payment(
    session: Session,
    payment_count: int,
    merchant_id: str,
    method_id: str,
    created: datetime,
    amount: int,
    status: str,
    error_code: str | None,
    delay_ms: int,
    event_status: str,
    rng: random.Random,
) -> int:
    order_id = f"O{payment_count:06d}"
    payment_id = f"P{payment_count:06d}"
    order_status = "paid" if status == "succeeded" else "created"
    session.add(
        Order(
            order_id=order_id,
            merchant_id=merchant_id,
            amount_cents=amount,
            currency="INR",
            status=order_status,
            created_at=created,
            updated_at=created,
            extra={"synthetic_customer_ref": f"CUST-{payment_count:06d}"},
        )
    )
    captured_at = created + timedelta(seconds=2) if status == "succeeded" else None
    session.add(
        Payment(
            payment_id=payment_id,
            order_id=order_id,
            merchant_id=merchant_id,
            method_id=method_id,
            amount_cents=amount,
            currency="INR",
            status=status,
            error_code=error_code,
            created_at=created,
            captured_at=captured_at,
            extra={"attempt": 1, "synthetic": True},
        )
    )
    delivered_at = created + timedelta(milliseconds=delay_ms) if event_status != "failed" else None
    if event_status == "delivered" and rng.random() < 0.03:
        event_status = "failed"
        delivered_at = None
    session.add(
        WebhookEvent(
            event_id=f"E{payment_count:06d}",
            payment_id=payment_id,
            event_type=f"payment.{status}",
            delivery_status=event_status,
            delay_ms=delay_ms,
            created_at=created,
            delivered_at=delivered_at,
            extra={"endpoint": "https://example.invalid/webhooks/payops", "synthetic": True},
        )
    )
    if status == "succeeded" and rng.random() < 0.04:
        session.add(
            Refund(
                refund_id=f"R{payment_count:06d}",
                payment_id=payment_id,
                amount_cents=max(amount // 2, 1),
                status="processed",
                created_at=created + timedelta(hours=6),
                extra={"reason": "customer_request", "synthetic": True},
            )
        )
    if status == "succeeded" and rng.random() < 0.01:
        session.add(
            Dispute(
                dispute_id=f"D{payment_count:06d}",
                payment_id=payment_id,
                reason="fraud",
                status="open",
                created_at=created + timedelta(days=2),
                extra={"synthetic": True},
            )
        )
    return payment_count + 1


def _outcome(
    rng: random.Random, merchant_id: str, method_id: str, created: datetime
) -> tuple[str, str | None, int]:
    delay_ms = rng.randint(80, 2_000)
    if (
        merchant_id == "M102"
        and method_id == "upi"
        and INCIDENT_UPI_SPIKE["start"] <= created < INCIDENT_UPI_SPIKE["end"]
    ):
        if rng.random() < 0.62:
            return "failed", "GATEWAY_TIMEOUT", delay_ms
    if (
        merchant_id == "M201"
        and INCIDENT_WEBHOOK_DELAY["start"] <= created < INCIDENT_WEBHOOK_DELAY["end"]
    ):
        delay_ms = rng.randint(45_000, 180_000)
        if rng.random() < 0.12:
            return "failed", "DO_NOT_HONOR", delay_ms
        return "succeeded", None, delay_ms
    if merchant_id == "M305":
        if rng.random() < 0.08:
            return "failed", "INSUFFICIENT_FUNDS", delay_ms
        return "succeeded", None, delay_ms
    if rng.random() < 0.07:
        code = rng.choice(["INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "AUTHENTICATION_FAILED"])
        return "failed", code, delay_ms
    return "succeeded", None, delay_ms


def _settlements(session: Session) -> None:
    created = datetime(2024, 6, 20, 0, 0, 0)
    for merchant_id, *_ in MERCHANTS:
        session.add(
            Settlement(
                settlement_id=f"S-{merchant_id}",
                merchant_id=merchant_id,
                amount_cents=1_000_000,
                currency="INR",
                status="settled",
                created_at=created,
                extra={"batch": "2024-06-20", "synthetic": True},
            )
        )
