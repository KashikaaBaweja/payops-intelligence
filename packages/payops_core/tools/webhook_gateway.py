from __future__ import annotations

import re
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from payops_core.data.models import Payment, WebhookEvent
from payops_core.models.schemas import (
    WebhookRequest,
    WebhookToolResult,
)
from payops_core.tools.webhook_analysis import (
    AnalyzedEvent,
    AnalyzedPayment,
    correlate_events,
    events_for_payment,
    find_delayed_events,
    find_duplicate_events,
    find_failed_deliveries,
    find_missing_events,
    find_retries,
)

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
FINDING_LIMIT = 100
WINDOW_REQUIRED = frozenset(
    {
        "find_missing_events",
        "find_delayed_events",
        "get_delivery_failures",
        "find_retries",
        "find_duplicate_events",
        "correlate_events_and_payments",
    }
)
ALLOWED_WEBHOOK_OPERATIONS: frozenset[str] = frozenset(
    {
        "get_events_for_payment",
        "find_missing_events",
        "find_delayed_events",
        "get_delivery_failures",
        "find_retries",
        "find_duplicate_events",
        "correlate_events_and_payments",
    }
)


class WebhookToolGateway:
    """Read-only catalog of webhook investigations. No raw SQL input."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._handlers: dict[str, Callable[[WebhookRequest], WebhookToolResult]] = {
            "get_events_for_payment": self._events_for_payment,
            "find_missing_events": self._missing,
            "find_delayed_events": self._delayed,
            "get_delivery_failures": self._failed,
            "find_retries": self._retries,
            "find_duplicate_events": self._duplicates,
            "correlate_events_and_payments": self._correlate,
        }

    def run(self, request: WebhookRequest) -> WebhookToolResult:
        if request.operation not in ALLOWED_WEBHOOK_OPERATIONS:
            raise ValueError(f"Unknown webhook operation: {request.operation}")
        _validate_id(request.merchant_id, "merchant_id")
        _validate_id(request.payment_id, "payment_id")
        if request.delay_threshold_ms < 0:
            raise ValueError("delay_threshold_ms must be >= 0")
        if request.operation in WINDOW_REQUIRED:
            if request.window is None:
                raise ValueError("time window is required")
            if request.window.end <= request.window.start:
                raise ValueError("time window end must be after start")
        if request.operation == "get_events_for_payment" and not request.payment_id:
            raise ValueError("get_events_for_payment requires payment_id")
        return self._handlers[request.operation](request)

    def _events_for_payment(self, request: WebhookRequest) -> WebhookToolResult:
        events = self._load_events(request)
        return self._wrap(request, events_for_payment(events, request.payment_id or ""))

    def _missing(self, request: WebhookRequest) -> WebhookToolResult:
        return self._wrap(
            request,
            find_missing_events(self._load_payments(request), self._load_events(request)),
        )

    def _delayed(self, request: WebhookRequest) -> WebhookToolResult:
        threshold = request.delay_threshold_ms
        return self._wrap(request, find_delayed_events(self._load_events(request), threshold))

    def _failed(self, request: WebhookRequest) -> WebhookToolResult:
        return self._wrap(request, find_failed_deliveries(self._load_events(request)))

    def _retries(self, request: WebhookRequest) -> WebhookToolResult:
        return self._wrap(request, find_retries(self._load_events(request)))

    def _duplicates(self, request: WebhookRequest) -> WebhookToolResult:
        return self._wrap(request, find_duplicate_events(self._load_events(request)))

    def _correlate(self, request: WebhookRequest) -> WebhookToolResult:
        return self._wrap(
            request,
            correlate_events(self._load_payments(request), self._load_events(request)),
        )

    def _load_events(self, request: WebhookRequest) -> list[AnalyzedEvent]:
        stmt = select(WebhookEvent, Payment).join(
            Payment, Payment.payment_id == WebhookEvent.payment_id
        )
        stmt = stmt.where(*self._predicates(request, event_time=True))
        rows = self.session.execute(stmt).all()
        return [_to_event(event, payment) for event, payment in rows]

    def _load_payments(self, request: WebhookRequest) -> list[AnalyzedPayment]:
        stmt = select(Payment).where(*self._predicates(request, event_time=False))
        return [_to_payment(payment) for payment in self.session.scalars(stmt).all()]

    def _predicates(self, request: WebhookRequest, *, event_time: bool) -> list[Any]:
        predicates: list[Any] = []
        stamp = WebhookEvent.created_at if event_time else Payment.created_at
        if request.window is not None:
            predicates.extend([stamp >= request.window.start, stamp < request.window.end])
        if request.merchant_id:
            predicates.append(Payment.merchant_id == request.merchant_id)
        if request.payment_id:
            predicates.append(Payment.payment_id == request.payment_id)
        return predicates

    def _wrap(self, request: WebhookRequest, findings: list) -> WebhookToolResult:
        limited = findings[:FINDING_LIMIT]
        filters = {
            "merchant_id": request.merchant_id,
            "payment_id": request.payment_id,
            "delay_threshold_ms": request.delay_threshold_ms,
        }
        return WebhookToolResult(
            operation=request.operation,
            findings=limited,
            count=len(limited),
            window=request.window,
            filters={key: value for key, value in filters.items() if value is not None},
        )


def _to_event(event: WebhookEvent, payment: Payment) -> AnalyzedEvent:
    extra = event.extra or {}
    return AnalyzedEvent(
        event_id=event.event_id,
        payment_id=event.payment_id,
        event_type=event.event_type,
        delivery_status=event.delivery_status,
        delay_ms=event.delay_ms,
        created_at=event.created_at,
        delivered_at=event.delivered_at,
        attempt=int(extra.get("attempt") or 1),
        idempotency_key=extra.get("idempotency_key"),
        order_id=payment.order_id,
        merchant_id=payment.merchant_id,
        payment_status=payment.status,
    )


def _to_payment(payment: Payment) -> AnalyzedPayment:
    return AnalyzedPayment(
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        merchant_id=payment.merchant_id,
        status=payment.status,
        created_at=payment.created_at,
    )


def _validate_id(value: str | None, field: str) -> None:
    if value is None:
        return
    if not _ID.match(value):
        raise ValueError(f"invalid {field}")
