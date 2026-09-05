"""Catalog of read-time payment consistency checks. Not a commit/rollback simulator."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from payops_core.data.models import Order, Payment, Refund, WebhookEvent
from payops_core.models.schemas import IntegrityCheck, IntegrityReport, TimeWindow

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SCHEMA_INVARIANTS = (
    "Consistency: CHECK failed payments must have an error_code",
    "Consistency: CHECK payment and order amounts are positive",
    "Consistency: FK RESTRICT keeps payments tied to orders and merchants",
    "Atomicity: a payment cannot be deleted while refunds or webhooks still reference it",
    "Durability: investigation_runs persist after the API store commits",
    "Isolation: not claimed — this check is single-writer read validation",
)


def validate_integrity(
    session: Session,
    merchant_id: str | None,
    window: TimeWindow,
) -> IntegrityReport:
    if merchant_id and not _ID.match(merchant_id):
        raise ValueError("invalid merchant_id")
    if window.end <= window.start:
        raise ValueError("time window end must be after start")

    predicates = _payment_predicates(merchant_id, window)
    sample_size = int(
        session.scalar(select(func.count()).select_from(Payment).where(*predicates)) or 0
    )
    checks = [
        _count_check(
            check_id="failed_has_error",
            name="Failed payments have an error code",
            observed=int(
                session.scalar(
                    select(func.count())
                    .select_from(Payment)
                    .where(*predicates, Payment.status == "failed", Payment.error_code.is_(None))
                )
                or 0
            ),
            invariant="failed ⇒ error_code IS NOT NULL",
            explanation="Failed rows without an error code break ops attribution.",
        ),
        _count_check(
            check_id="succeeded_has_capture",
            name="Succeeded payments have captured_at",
            observed=int(
                session.scalar(
                    select(func.count())
                    .select_from(Payment)
                    .where(
                        *predicates,
                        Payment.status == "succeeded",
                        Payment.captured_at.is_(None),
                    )
                )
                or 0
            ),
            invariant="succeeded ⇒ captured_at IS NOT NULL",
            explanation="A captured payment without captured_at is an incomplete write.",
        ),
        _count_check(
            check_id="amount_positive",
            name="Payment amounts are positive",
            observed=int(
                session.scalar(
                    select(func.count())
                    .select_from(Payment)
                    .where(*predicates, Payment.amount_cents <= 0)
                )
                or 0
            ),
            invariant="amount_cents > 0",
            explanation="Non-positive amounts violate the payments CHECK constraint.",
        ),
        _count_check(
            check_id="merchant_matches_order",
            name="Payment merchant matches order merchant",
            observed=int(
                session.scalar(
                    select(func.count())
                    .select_from(Payment)
                    .join(Order, Payment.order_id == Order.order_id)
                    .where(*predicates, Payment.merchant_id != Order.merchant_id)
                )
                or 0
            ),
            invariant="payment.merchant_id = order.merchant_id",
            explanation="A merchant mismatch is a cross-tenant consistency break.",
        ),
        _count_check(
            check_id="refunds_within_payment",
            name="Refund totals do not exceed the payment",
            observed=_over_refunded(session, predicates),
            invariant="sum(refunds.amount_cents) <= payment.amount_cents",
            explanation="Refunds larger than the original payment are inconsistent.",
        ),
        _count_check(
            check_id="webhooks_reference_payments",
            name="Webhook events reference an existing payment",
            observed=_orphan_webhooks(session, merchant_id, window),
            invariant="webhook_events.payment_id exists in payments",
            explanation="Orphan webhook rows would mean a broken foreign key.",
        ),
    ]
    passed = all(item.passed for item in checks)
    return IntegrityReport(
        merchant_id=merchant_id,
        window=window,
        passed=passed,
        sample_size=sample_size,
        checks=checks,
        schema_invariants=list(SCHEMA_INVARIANTS),
        notes=(
            "Read-time consistency validation against schema invariants. "
            "This is not an ACID commit/rollback classroom simulator."
        ),
    )


def _payment_predicates(merchant_id: str | None, window: TimeWindow) -> list:
    predicates = [Payment.created_at >= window.start, Payment.created_at < window.end]
    if merchant_id:
        predicates.append(Payment.merchant_id == merchant_id)
    return predicates


def _count_check(
    *,
    check_id: str,
    name: str,
    observed: int,
    invariant: str,
    explanation: str,
) -> IntegrityCheck:
    return IntegrityCheck(
        check_id=check_id,
        name=name,
        passed=observed == 0,
        observed=observed,
        invariant=invariant,
        explanation=explanation,
    )


def _over_refunded(session: Session, predicates: list) -> int:
    totals = (
        select(Refund.payment_id, func.sum(Refund.amount_cents).label("refunded"))
        .group_by(Refund.payment_id)
        .subquery()
    )
    return int(
        session.scalar(
            select(func.count())
            .select_from(Payment)
            .join(totals, Payment.payment_id == totals.c.payment_id)
            .where(*predicates, totals.c.refunded > Payment.amount_cents)
        )
        or 0
    )


def _orphan_webhooks(session: Session, merchant_id: str | None, window: TimeWindow) -> int:
    del merchant_id
    return int(
        session.scalar(
            select(func.count())
            .select_from(WebhookEvent)
            .outerjoin(Payment, WebhookEvent.payment_id == Payment.payment_id)
            .where(
                WebhookEvent.created_at >= window.start,
                WebhookEvent.created_at < window.end,
                Payment.payment_id.is_(None),
            )
        )
        or 0
    )
