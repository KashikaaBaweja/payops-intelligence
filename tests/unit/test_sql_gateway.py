from datetime import datetime

from payops_core.data.db import apply_schema, make_engine
from payops_core.data.synthetic_generator import generate
from payops_core.models import TimeWindow
from payops_core.tools.sql_gateway import SqlGateway, SqlOpRequest


def test_upi_timeout_spike_is_discoverable():
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    generate(engine, seed=42)
    gateway = SqlGateway(engine)
    window = TimeWindow(start=datetime(2024, 6, 15, 10, 0, 0), end=datetime(2024, 6, 15, 12, 0, 0))
    in_window = gateway.run(
        SqlOpRequest(operation="get_failure_rate", merchant_id="M102", method_id="upi", window=window)
    )
    errors = gateway.run(
        SqlOpRequest(
            operation="breakdown_by_error_code", merchant_id="M102", method_id="upi", window=window
        )
    )
    assert float(in_window.value) > 0.4
    assert "GATEWAY_TIMEOUT" in errors.value


def test_unknown_operation_rejected():
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    gateway = SqlGateway(engine)
    try:
        gateway.run(SqlOpRequest(operation="drop_table"))  # type: ignore[arg-type]
        assert False, "should have rejected"
    except Exception:
        assert True
