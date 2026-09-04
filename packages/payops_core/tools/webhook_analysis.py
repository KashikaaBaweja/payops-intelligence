from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from payops_core.models.schemas import WebhookFinding

DELAY_THRESHOLD_MS = 30_000
TERMINAL_PAYMENT_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass(frozen=True)
class AnalyzedEvent:
    event_id: str
    payment_id: str
    event_type: str
    delivery_status: str
    delay_ms: int
    created_at: datetime
    delivered_at: datetime | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    order_id: str | None = None
    merchant_id: str | None = None
    payment_status: str | None = None


@dataclass(frozen=True)
class AnalyzedPayment:
    payment_id: str
    order_id: str
    merchant_id: str
    status: str
    created_at: datetime


def classify_delivery(event: AnalyzedEvent, threshold_ms: int = DELAY_THRESHOLD_MS) -> str:
    if event.delivery_status == "failed":
        return "failed"
    if event.delay_ms >= threshold_ms or event.delivery_status == "delayed":
        return "delayed"
    if event.delivery_status == "delivered":
        return "normal"
    return event.delivery_status


def find_delayed_events(
    events: list[AnalyzedEvent],
    threshold_ms: int = DELAY_THRESHOLD_MS,
) -> list[WebhookFinding]:
    return [
        _event_finding(event, "delayed")
        for event in _sorted(events)
        if classify_delivery(event, threshold_ms) == "delayed"
    ]


def find_failed_deliveries(events: list[AnalyzedEvent]) -> list[WebhookFinding]:
    return [
        _event_finding(event, "failed")
        for event in _sorted(events)
        if event.delivery_status == "failed"
    ]


def find_missing_events(
    payments: list[AnalyzedPayment],
    events: list[AnalyzedEvent],
) -> list[WebhookFinding]:
    by_payment: dict[str, list[AnalyzedEvent]] = defaultdict(list)
    for event in events:
        by_payment[event.payment_id].append(event)
    findings: list[WebhookFinding] = []
    for payment in payments:
        if payment.status not in TERMINAL_PAYMENT_STATUSES:
            continue
        related = by_payment.get(payment.payment_id, [])
        if related:
            continue
        expected = f"payment.{payment.status}"
        findings.append(
            WebhookFinding(
                kind="missing",
                payment_id=payment.payment_id,
                order_id=payment.order_id,
                merchant_id=payment.merchant_id,
                event_ids=[event.event_id for event in related],
                event_type=expected,
                details={"payment_status": payment.status, "event_count": len(related)},
            )
        )
    return findings


def find_retries(events: list[AnalyzedEvent]) -> list[WebhookFinding]:
    findings: list[WebhookFinding] = []
    for key, group in _groups(events).items():
        payment_id, event_type = key
        if len(group) < 2:
            continue
        attempts = [event.attempt for event in group]
        if len(set(attempts)) != len(attempts) or max(attempts) <= min(attempts):
            continue
        ordered = sorted(group, key=lambda event: (event.attempt, event.created_at))
        findings.append(
            WebhookFinding(
                kind="retry",
                payment_id=payment_id,
                order_id=ordered[0].order_id,
                merchant_id=ordered[0].merchant_id,
                event_ids=[event.event_id for event in ordered],
                event_type=event_type,
                details={
                    "attempts": [event.attempt for event in ordered],
                    "statuses": [event.delivery_status for event in ordered],
                },
            )
        )
    return findings


def find_duplicate_events(events: list[AnalyzedEvent]) -> list[WebhookFinding]:
    findings: list[WebhookFinding] = []
    seen: set[tuple[str, ...]] = set()
    keyed: dict[tuple[str, str, str], list[AnalyzedEvent]] = defaultdict(list)
    same_attempt: dict[tuple[str, str, int], list[AnalyzedEvent]] = defaultdict(list)
    for event in events:
        if event.idempotency_key:
            keyed[(event.payment_id, event.event_type, event.idempotency_key)].append(event)
        same_attempt[(event.payment_id, event.event_type, event.attempt)].append(event)
    for group in list(keyed.values()) + list(same_attempt.values()):
        if len(group) < 2:
            continue
        event_ids = tuple(sorted(event.event_id for event in group))
        if event_ids in seen:
            continue
        seen.add(event_ids)
        ordered = _sorted(group)
        findings.append(
            WebhookFinding(
                kind="duplicate",
                payment_id=ordered[0].payment_id,
                order_id=ordered[0].order_id,
                merchant_id=ordered[0].merchant_id,
                event_ids=list(event_ids),
                event_type=ordered[0].event_type,
                details={
                    "idempotency_key": ordered[0].idempotency_key,
                    "attempt": ordered[0].attempt,
                    "count": len(ordered),
                },
            )
        )
    return findings


def correlate_events(
    payments: list[AnalyzedPayment],
    events: list[AnalyzedEvent],
) -> list[WebhookFinding]:
    payments_by_id = {payment.payment_id: payment for payment in payments}
    findings: list[WebhookFinding] = []
    for event in _sorted(events):
        payment = payments_by_id.get(event.payment_id)
        if payment is None:
            findings.append(
                _event_finding(event, "mismatch", extra={"reason": "payment_not_found"})
            )
            continue
        expected = f"payment.{payment.status}"
        if event.event_type.startswith("payment.") and event.event_type != expected:
            findings.append(
                _event_finding(
                    event,
                    "mismatch",
                    extra={
                        "reason": "event_type_mismatch",
                        "payment_status": payment.status,
                        "expected_event_type": expected,
                    },
                )
            )
    return findings


def events_for_payment(events: list[AnalyzedEvent], payment_id: str) -> list[WebhookFinding]:
    return [
        _event_finding(event, "event")
        for event in _sorted(events)
        if event.payment_id == payment_id
    ]


def _event_finding(
    event: AnalyzedEvent,
    kind: str,
    extra: dict | None = None,
) -> WebhookFinding:
    return WebhookFinding(
        kind=kind,  # type: ignore[arg-type]
        payment_id=event.payment_id,
        order_id=event.order_id,
        merchant_id=event.merchant_id,
        event_ids=[event.event_id],
        event_type=event.event_type,
        delivery_status=event.delivery_status,
        delay_ms=event.delay_ms,
        details={
            "attempt": event.attempt,
            "idempotency_key": event.idempotency_key,
            "payment_status": event.payment_status,
            **(extra or {}),
        },
    )


def _sorted(events: list[AnalyzedEvent]) -> list[AnalyzedEvent]:
    return sorted(events, key=lambda event: (event.created_at, event.event_id))


def _groups(events: list[AnalyzedEvent]) -> dict[tuple[str, str], list[AnalyzedEvent]]:
    grouped: dict[tuple[str, str], list[AnalyzedEvent]] = defaultdict(list)
    for event in events:
        grouped[(event.payment_id, event.event_type)].append(event)
    return grouped
