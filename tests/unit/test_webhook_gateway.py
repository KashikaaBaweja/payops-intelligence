import pytest
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.data.synthetic_generator import INCIDENT_WEBHOOK_DELAY
from payops_core.models.schemas import TimeWindow, WebhookRequest
from payops_core.tools import WebhookToolGateway
from pydantic import ValidationError
from sqlalchemy.orm import Session

from tests.webhook_fixtures import WEBHOOK_WINDOW, load_known_webhook_dataset


def _gateway() -> tuple[Session, WebhookToolGateway]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_known_webhook_dataset(session)
    session.commit()
    return session, WebhookToolGateway(session)


def _request(operation: str, **kwargs) -> WebhookRequest:
    payload = {"operation": operation, "window": WEBHOOK_WINDOW, "merchant_id": "M201", **kwargs}
    return WebhookRequest(**payload)


def test_gateway_classifies_known_webhook_cases() -> None:
    session, gateway = _gateway()
    delayed = gateway.run(_request("find_delayed_events"))
    failed = gateway.run(_request("get_delivery_failures"))
    missing = gateway.run(_request("find_missing_events"))
    retries = gateway.run(_request("find_retries"))
    duplicates = gateway.run(_request("find_duplicate_events"))
    correlated = gateway.run(_request("correlate_events_and_payments"))
    events = gateway.run(WebhookRequest(operation="get_events_for_payment", payment_id="PWH001"))
    assert [item.payment_id for item in delayed.findings] == ["PWH002"]
    assert [item.payment_id for item in failed.findings] == ["PWH003", "PWH005"]
    assert [item.payment_id for item in missing.findings] == ["PWH004"]
    assert retries.findings[0].event_ids == ["EWH005A", "EWH005B"]
    assert set(duplicates.findings[0].event_ids) == {"EWH006A", "EWH006B"}
    assert correlated.findings[0].payment_id == "PWH007"
    assert events.count == 1
    assert events.tool == "webhook_gateway"
    assert delayed.filters["merchant_id"] == "M201"
    session.close()


def test_gateway_rejects_sql_and_unknown_operations() -> None:
    with pytest.raises(ValidationError):
        WebhookRequest(
            operation="find_delayed_events",
            window=WEBHOOK_WINDOW,
            sql="SELECT * FROM webhook_events",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        WebhookRequest(operation="drop_events", window=WEBHOOK_WINDOW)  # type: ignore[arg-type]


def test_seeded_delay_incident_is_detectable(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'wh.db'}"
    seed(url, rng_seed=42)
    factory = session_factory(make_engine(url))
    with factory() as session:
        gateway = WebhookToolGateway(session)
        result = gateway.run(
            WebhookRequest(
                operation="find_delayed_events",
                window=TimeWindow(
                    start=INCIDENT_WEBHOOK_DELAY["start"],
                    end=INCIDENT_WEBHOOK_DELAY["end"],
                ),
                merchant_id="M201",
            )
        )
        assert result.count > 10
        assert all(item.kind == "delayed" for item in result.findings)
