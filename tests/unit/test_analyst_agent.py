import pytest
from payops_core.agents import DataAnalystAgent
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.data.synthetic_generator import INCIDENT_UPI_SPIKE
from payops_core.models.schemas import AnalystResult, Task, TimeWindow
from sqlalchemy.orm import Session

from tests.analytics_fixtures import CURRENT_WINDOW, PREVIOUS_WINDOW, load_known_ops_dataset


def _agent() -> tuple[Session, DataAnalystAgent]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_known_ops_dataset(session)
    session.commit()
    return session, DataAnalystAgent(session)


def test_agent_runs_success_rate_for_known_dataset() -> None:
    session, agent = _agent()
    result = agent.analyze(
        "What is the payment success rate for M102?",
        window=CURRENT_WINDOW,
    )
    assert result.operations == ["get_success_rate"]
    metric = result.metrics[0]
    assert metric.value == 0.833333
    assert metric.filters["merchant_id"] == "M102"
    assert metric.tool == "sql_gateway"
    assert "answer" not in AnalystResult.model_fields
    assert "executive_summary" not in AnalystResult.model_fields
    session.close()


def test_agent_runs_multiple_operations() -> None:
    session, agent = _agent()
    result = agent.analyze(
        "Failure rate and error-code breakdown for M102",
        window=CURRENT_WINDOW,
    )
    assert result.operations == ["get_failure_rate", "breakdown_by_error_code"]
    by_name = {item.metric: item.value for item in result.metrics}
    assert by_name["failure_rate"] == 0.166667
    assert by_name["error_code_breakdown"]["GATEWAY_TIMEOUT"]["count"] == 2
    session.close()


def test_agent_merchant_and_window_comparison() -> None:
    session, agent = _agent()
    result = agent.analyze(
        "Compare success rate for M102 vs M201 versus the previous window",
        window=CURRENT_WINDOW,
        previous_window=PREVIOUS_WINDOW,
    )
    assert "compare_merchants" in result.operations
    assert "compare_time_windows" in result.operations
    merchants = next(item for item in result.metrics if item.metric == "merchant_comparison")
    assert merchants.value["M102"] == 0.833333
    assert merchants.value["M201"] == 0.8
    session.close()


def test_agent_only_runs_query_metrics_tasks() -> None:
    session, agent = _agent()
    result = agent.analyze(
        "unused",
        window=CURRENT_WINDOW,
        task=Task(
            task_id="t1",
            task_type="query_metrics",
            rationale="success",
            query="get_success_rate",
            merchant_id="M102",
        ),
    )
    assert result.operations == ["get_success_rate"]
    with pytest.raises(ValueError, match="query_metrics"):
        agent.analyze(
            "docs",
            window=CURRENT_WINDOW,
            task=Task(task_id="t2", task_type="retrieve_docs", rationale="docs"),
        )
    session.close()


def test_seeded_upi_incident_has_deterministic_failure_spike(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'seeded.db'}"
    seed(url, rng_seed=42)
    factory = session_factory(make_engine(url))
    with factory() as session:
        agent = DataAnalystAgent(session)
        window = TimeWindow(start=INCIDENT_UPI_SPIKE["start"], end=INCIDENT_UPI_SPIKE["end"])
        result = agent.analyze(
            "Failure rate and error-code breakdown for M102 UPI",
            window=window,
            merchant_id="M102",
            method_id="upi",
        )
        by_name = {item.metric: item for item in result.metrics}
        assert by_name["failure_rate"].value == 0.8
        assert by_name["failure_rate"].sample_size == 40
        errors = by_name["error_code_breakdown"].value
        assert errors["GATEWAY_TIMEOUT"]["count"] == 32
        assert errors["GATEWAY_TIMEOUT"]["share"] == 1.0
