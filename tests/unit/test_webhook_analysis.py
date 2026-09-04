from datetime import datetime

from payops_core.tools.webhook_analysis import (
    AnalyzedEvent,
    AnalyzedPayment,
    classify_delivery,
    correlate_events,
    events_for_payment,
    find_delayed_events,
    find_duplicate_events,
    find_failed_deliveries,
    find_missing_events,
    find_retries,
)

CREATED = datetime(2024, 6, 18, 14, 10, 0)


def _event(**kwargs) -> AnalyzedEvent:
    payload = {
        "event_id": "E1",
        "payment_id": "PWH001",
        "event_type": "payment.succeeded",
        "delivery_status": "delivered",
        "delay_ms": 90,
        "created_at": CREATED,
        "attempt": 1,
        "order_id": "OWH001",
        "merchant_id": "M201",
        "payment_status": "succeeded",
    }
    payload.update(kwargs)
    return AnalyzedEvent(**payload)


def _payment(**kwargs) -> AnalyzedPayment:
    payload = {
        "payment_id": "PWH001",
        "order_id": "OWH001",
        "merchant_id": "M201",
        "status": "succeeded",
        "created_at": CREATED,
    }
    payload.update(kwargs)
    return AnalyzedPayment(**payload)


def test_normal_event_is_not_delayed_or_failed() -> None:
    event = _event()
    assert classify_delivery(event) == "normal"
    assert find_delayed_events([event]) == []
    assert find_failed_deliveries([event]) == []
    assert events_for_payment([event], "PWH001")[0].kind == "event"


def test_delayed_events() -> None:
    delayed = _event(event_id="E2", payment_id="PWH002", delay_ms=60_000, delivery_status="delayed")
    assert classify_delivery(delayed) == "delayed"
    findings = find_delayed_events([_event(), delayed])
    assert [item.payment_id for item in findings] == ["PWH002"]
    assert findings[0].delay_ms == 60_000


def test_failed_deliveries() -> None:
    failed = _event(event_id="E3", payment_id="PWH003", delivery_status="failed", delay_ms=0)
    findings = find_failed_deliveries([_event(), failed])
    assert [item.payment_id for item in findings] == ["PWH003"]


def test_retries_are_grouped_by_attempt() -> None:
    first = _event(
        event_id="E5A",
        payment_id="PWH005",
        delivery_status="failed",
        attempt=1,
        idempotency_key="retry-a",
    )
    second = _event(
        event_id="E5B",
        payment_id="PWH005",
        attempt=2,
        idempotency_key="retry-b",
    )
    findings = find_retries([first, second, _event()])
    assert len(findings) == 1
    assert findings[0].kind == "retry"
    assert findings[0].event_ids == ["E5A", "E5B"]
    assert find_duplicate_events([first, second]) == []


def test_duplicates_share_idempotency_key_or_attempt() -> None:
    left = _event(event_id="E6A", payment_id="PWH006", idempotency_key="dup-006", attempt=1)
    right = _event(event_id="E6B", payment_id="PWH006", idempotency_key="dup-006", attempt=1)
    findings = find_duplicate_events([left, right, _event()])
    assert len(findings) == 1
    assert set(findings[0].event_ids) == {"E6A", "E6B"}
    assert find_retries([left, right]) == []


def test_missing_and_correlation_mismatch() -> None:
    payments = [
        _payment(),
        _payment(payment_id="PWH004", order_id="OWH004"),
        _payment(payment_id="PWH007", order_id="OWH007"),
    ]
    events = [
        _event(),
        _event(
            event_id="E7",
            payment_id="PWH007",
            event_type="payment.failed",
            order_id="OWH007",
        ),
    ]
    missing = find_missing_events(payments, events)
    assert [item.payment_id for item in missing] == ["PWH004"]
    mismatches = correlate_events(payments, events)
    assert mismatches[0].kind == "mismatch"
    assert mismatches[0].payment_id == "PWH007"
    assert mismatches[0].details["reason"] == "event_type_mismatch"
