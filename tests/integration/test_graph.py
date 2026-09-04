from datetime import datetime

from payops_core.data.db import apply_schema, make_engine
from payops_core.data.synthetic_generator import generate
from payops_core.graph.build_graph import build_graph, initial_state
from payops_core.llm import DemoLLM
from payops_core.models import TimeWindow
from payops_core.rag.vector_store import build_store
from payops_core.tools.sql_gateway import SqlGateway


def _graph():
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    generate(engine, seed=42)
    build_store()
    return build_graph(llm=DemoLLM(), gateway=SqlGateway(engine))


def test_m102_investigation_names_gateway_timeout():
    graph = _graph()
    state = initial_state(
        "Why did Merchant M102 payment success rate drop 10:00-12:00 on 15 Jun 2024?",
        merchant_id="M102",
        time_window=TimeWindow(start=datetime(2024, 6, 15, 10, 0, 0), end=datetime(2024, 6, 15, 12, 0, 0)),
    )
    result = graph.invoke(state)
    report = result["report"]
    assert report.evidence_sufficient is True
    assert "timeout" in report.likely_cause.cause.lower() or "upi" in report.likely_cause.cause.lower()
    assert any(event.agent == "planner" for event in result["trace"])


def test_m305_investigation_is_insufficient():
    graph = _graph()
    state = initial_state(
        "Something is wrong with M305. Find the root cause.",
        merchant_id="M305",
        time_window=TimeWindow(start=datetime(2024, 5, 1, 0, 0, 0), end=datetime(2024, 5, 2, 0, 0, 0)),
    )
    result = graph.invoke(state)
    assert result["report"].evidence_sufficient is False
