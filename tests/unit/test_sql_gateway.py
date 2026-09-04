import pytest
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.models.schemas import AnalyticsRequest
from payops_core.tools import SqlToolGateway
from pydantic import ValidationError
from sqlalchemy.orm import Session

from tests.analytics_fixtures import CURRENT_WINDOW, PREVIOUS_WINDOW, load_known_ops_dataset


def _gateway() -> tuple[Session, SqlToolGateway]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_known_ops_dataset(session)
    session.commit()
    return session, SqlToolGateway(session)


def _request(**kwargs) -> AnalyticsRequest:
    payload = {"window": CURRENT_WINDOW, "merchant_id": "M102", **kwargs}
    return AnalyticsRequest(**payload)


def test_success_and_failure_rates_are_exact() -> None:
    session, gateway = _gateway()
    success = gateway.run(_request(operation="get_success_rate"))
    failure = gateway.run(_request(operation="get_failure_rate"))
    assert success.metric == "success_rate"
    assert success.value == 0.833333
    assert success.sample_size == 12
    assert failure.value == 0.166667
    _assert_result_shape(success)
    session.close()


def test_method_and_error_breakdowns() -> None:
    session, gateway = _gateway()
    methods = gateway.run(_request(operation="breakdown_by_method"))
    errors = gateway.run(_request(operation="breakdown_by_error_code"))
    assert methods.value["upi"]["total"] == 10
    assert methods.value["upi"]["failed"] == 2
    assert methods.value["upi"]["success_rate"] == 0.8
    assert methods.value["card"]["total"] == 2
    assert errors.value == {"GATEWAY_TIMEOUT": {"count": 2, "share": 1.0}}
    session.close()


def test_time_window_and_merchant_comparison() -> None:
    session, gateway = _gateway()
    windows = gateway.run(
        _request(operation="compare_time_windows", previous_window=PREVIOUS_WINDOW)
    )
    merchants = gateway.run(
        _request(operation="compare_merchants", compare_merchant_id="M201")
    )
    assert windows.value["current"] == 0.833333
    assert windows.value["previous"] == 1.0
    assert windows.value["delta"] == -0.166667
    assert merchants.value["M102"] == 0.833333
    assert merchants.value["M201"] == 0.8
    assert merchants.value["delta"] == 0.033333
    session.close()


def test_refund_dispute_and_webhook_rates() -> None:
    session, gateway = _gateway()
    refunds = gateway.run(_request(operation="get_refund_rate"))
    disputes = gateway.run(_request(operation="get_dispute_rate"))
    webhooks = gateway.run(_request(operation="get_webhook_failure_rate"))
    assert refunds.value == 0.2
    assert refunds.source == "refunds"
    assert disputes.value == 0.1
    assert disputes.source == "disputes"
    assert webhooks.value == 0.166667
    assert webhooks.source == "webhook_events"
    session.close()


def test_method_filter_changes_success_rate() -> None:
    session, gateway = _gateway()
    upi = gateway.run(_request(operation="get_success_rate", method_id="upi"))
    assert upi.value == 0.8
    assert upi.sample_size == 10
    assert upi.filters["method_id"] == "upi"
    session.close()


def test_invalid_identifier_is_rejected() -> None:
    session, gateway = _gateway()
    with pytest.raises(ValueError, match="invalid merchant_id"):
        gateway.run(_request(operation="get_success_rate", merchant_id="M102;drop"))
    session.close()
    session, gateway = _gateway()
    empty = gateway.run(
        AnalyticsRequest(
            operation="get_success_rate",
            window=CURRENT_WINDOW.model_copy(
                update={"start": CURRENT_WINDOW.end, "end": CURRENT_WINDOW.end.replace(hour=14)}
            ),
            merchant_id="M102",
        )
    )
    assert empty.value == 0.0
    assert empty.sample_size == 0
    assert empty.notes == "no rows in window"
    session.close()


def test_unknown_operation_and_raw_sql_are_rejected() -> None:
    session, gateway = _gateway()
    with pytest.raises(ValidationError):
        AnalyticsRequest(
            operation="drop_tables",  # type: ignore[arg-type]
            window=CURRENT_WINDOW,
        )
    with pytest.raises(ValidationError):
        AnalyticsRequest(
            operation="get_success_rate",
            window=CURRENT_WINDOW,
            sql="SELECT * FROM payments",  # type: ignore[call-arg]
        )
    session.close()


def _assert_result_shape(result) -> None:
    assert result.metric
    assert result.value is not None
    assert result.window == CURRENT_WINDOW
    assert result.filters["merchant_id"] == "M102"
    assert result.tool == "sql_gateway"
    assert result.source
    assert result.operation
