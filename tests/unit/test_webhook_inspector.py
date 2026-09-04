import pytest
from payops_core.agents import WebhookInspectorAgent
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.models.schemas import Task, WebhookInspectorResult
from sqlalchemy.orm import Session

from tests.webhook_fixtures import WEBHOOK_WINDOW, load_known_webhook_dataset


def _agent() -> tuple[Session, WebhookInspectorAgent]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_known_webhook_dataset(session)
    session.commit()
    return session, WebhookInspectorAgent(session)


def test_inspector_finds_delayed_events() -> None:
    session, agent = _agent()
    result = agent.inspect("Find delayed webhook events for M201", window=WEBHOOK_WINDOW)
    assert result.operations == ["find_delayed_events"]
    assert result.results[0].findings[0].payment_id == "PWH002"
    assert result.evidence.items
    assert result.evidence.items[0].source == "webhook"
    assert "answer" not in WebhookInspectorResult.model_fields
    session.close()


def test_inspector_runs_multiple_webhook_checks() -> None:
    session, agent = _agent()
    result = agent.inspect(
        "Check missing events, retries and duplicates for M201",
        window=WEBHOOK_WINDOW,
    )
    assert result.operations == [
        "find_missing_events",
        "find_retries",
        "find_duplicate_events",
    ]
    by_op = {item.operation: item for item in result.results}
    assert by_op["find_missing_events"].findings[0].payment_id == "PWH004"
    assert by_op["find_retries"].findings[0].payment_id == "PWH005"
    assert by_op["find_duplicate_events"].findings[0].payment_id == "PWH006"
    session.close()


def test_inspector_only_runs_inspect_webhooks_tasks() -> None:
    session, agent = _agent()
    result = agent.inspect(
        "unused",
        window=WEBHOOK_WINDOW,
        task=Task(
            task_id="t1",
            task_type="inspect_webhooks",
            rationale="failed deliveries",
            query="get_delivery_failures",
            merchant_id="M201",
        ),
    )
    assert result.operations == ["get_delivery_failures"]
    with pytest.raises(ValueError, match="inspect_webhooks"):
        agent.inspect(
            "metrics",
            window=WEBHOOK_WINDOW,
            task=Task(task_id="t2", task_type="query_metrics", rationale="metrics"),
        )
    session.close()
