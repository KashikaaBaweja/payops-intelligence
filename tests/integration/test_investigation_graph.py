from pathlib import Path

import pytest
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.graph.build import report_from, run_investigation
from payops_core.models.schemas import TraceEvent
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"
SAFE_TRACE_FIELDS = {
    "node",
    "action",
    "tool",
    "search_query",
    "evidence_ids",
    "decision",
    "verification_status",
    "timestamp",
}


@pytest.fixture(scope="module")
def graph_deps(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("graph") / "payops.db"
    url = f"sqlite:///{db_path}"
    seed(url, rng_seed=42)
    store, _count = ingest_corpus(CORPUS, store=InMemoryVectorStore())
    engine = make_engine(url)
    return engine, DocumentRetriever(store)


def _run(graph_deps, question: str, **kwargs):
    engine, retriever = graph_deps
    factory = session_factory(engine)
    with factory() as session:
        return run_investigation(question, retriever=retriever, session=session, **kwargs)


def _nodes(state) -> list[str]:
    return [event.node for event in state.get("trace") or []]


def _assert_safe_trace(state) -> None:
    assert set(TraceEvent.model_fields) == SAFE_TRACE_FIELDS
    for event in state.get("trace") or []:
        assert event.node
        assert event.action
        assert not hasattr(event, "reasoning")
        assert not hasattr(event, "scratchpad")


def test_simple_question(graph_deps) -> None:
    state = _run(graph_deps, "What is the payment lifecycle?")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["retrieve_docs"]
    assert any(item.source == "doc" for item in state["evidence"].items)
    assert "investigate" in _nodes(state)
    assert "writer" in _nodes(state)
    assert report.evidence_sufficient is True
    assert "sufficiency" in _nodes(state)


def test_rag_only_question(graph_deps) -> None:
    state = _run(graph_deps, "What does GATEWAY_TIMEOUT mean?")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["retrieve_docs"]
    combined = " ".join(item.text_snippet for item in state["evidence"].items)
    assert "GATEWAY_TIMEOUT" in combined
    assert all(item.source == "doc" for item in state["evidence"].items)
    assert report.evidence_sufficient is True
    assert "incident_risk" in _nodes(state)
    assert "verifier" in _nodes(state)
    assert report.retrieval is not None
    assert report.retrieval.rounds
    assert report.retrieval.latency_ms >= 0
    assert any(event.action == "rag_search" for event in state["trace"])


def test_sql_required_question(graph_deps) -> None:
    state = _run(graph_deps, "What is the payment success rate for M102?")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["query_metrics"]
    assert any(item.source == "metric" for item in state["evidence"].items)
    assert any(metric.metric == "success_rate" for metric in state["metrics"])
    assert report.evidence_sufficient is True
    assert any(event.tool for event in state["trace"] if event.node == "investigate")


def test_webhook_required_question(graph_deps) -> None:
    state = _run(graph_deps, "Find delayed webhook events for M201")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["inspect_webhooks"]
    assert any(item.source == "webhook" for item in state["evidence"].items)
    assert any(item.metadata.get("kind") == "delayed" for item in state["evidence"].items)
    assert report.evidence_sufficient is True


def test_merchant_health_scorecard(graph_deps) -> None:
    state = _run(graph_deps, "Merchant health scorecard for Harbor Retail M102")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["merchant_health"]
    assert any(item.source == "health" for item in state["evidence"].items)
    assert report.evidence_sufficient is True
    assert "Incomplete investigation" not in report.executive_summary


def test_integrity_question_uses_catalog_not_simulator(graph_deps) -> None:
    state = _run(
        graph_deps,
        "Are Harbor Retail M102 payments transactionally consistent under ACID invariants?",
    )
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == ["validate_integrity"]
    items = [item for item in state["evidence"].items if item.source == "integrity"]
    assert items
    assert items[0].metadata.get("passed") is True
    assert "consistency violations" in report.likely_cause.cause.lower()
    assert "classroom" not in report.executive_summary.lower()
    assert report.evidence_sufficient is True


def test_ml_risk_triggers_metrics_not_fraud_decision(graph_deps) -> None:
    state = _run(graph_deps, "What is the predicted payment risk and expected loss for M102?")
    report = report_from(state)
    _assert_safe_trace(state)
    assert [task.task_type for task in state["plan"].tasks] == [
        "score_risk",
        "query_metrics",
        "score_regression",
    ]
    sources = {item.source for item in state["evidence"].items}
    assert "ml" in sources
    assert "metric" in sources
    assert report.evidence_sufficient is True
    assert "fraudulent" not in report.likely_cause.cause.lower()
    assert all("is fraudulent" not in action.lower() for action in report.recommended_actions)


def test_planned_tasks_drain_in_one_visit(graph_deps) -> None:
    state = _run(
        graph_deps,
        "Why did Harbor Retail M102 UPI payments fail with GATEWAY_TIMEOUT?",
    )
    report = report_from(state)
    _assert_safe_trace(state)
    types = [task.task_type for task in state["plan"].tasks]
    assert "retrieve_docs" in types
    assert "query_metrics" in types
    investigate_runs = [
        event
        for event in state["trace"]
        if event.node == "investigate" and event.action == "run_task"
    ]
    assert {event.decision for event in investigate_runs} >= {"retrieve_docs", "query_metrics"}
    sources = {item.source for item in state["evidence"].items}
    assert "doc" in sources
    assert "metric" in sources
    assert state["iteration"] == 1
    assert "refine" not in _nodes(state)
    assert report.evidence_sufficient is True


def test_unsupported_conclusion_requests_more_investigation(graph_deps, monkeypatch) -> None:
    from payops_core.agents.incident import IncidentRiskAgent
    from payops_core.models.schemas import Hypothesis

    def _incorrect(_self, evidence, _metrics, _question):
        return [
            Hypothesis(
                cause="The outage was caused by a lunar radiation event",
                supporting_evidence_ids=list(evidence.ids()[:1]),
                confidence=0.95,
                category="processor",
            )
        ]

    monkeypatch.setattr(IncidentRiskAgent, "propose", _incorrect)
    state = _run(graph_deps, "What does GATEWAY_TIMEOUT mean?")
    report = report_from(state)
    _assert_safe_trace(state)
    nodes = _nodes(state)
    assert "verifier" in nodes
    assert "refine" in nodes
    assert nodes.index("verifier") < nodes.index("refine")
    assert any(event.node == "refine" and event.action == "queue_gaps" for event in state["trace"])
    assert state.get("verification") is not None
    assert state["verification"].needs_more_evidence is True
    assert report.evidence_sufficient is False
    assert "lunar radiation" not in report.likely_cause.cause
    assert any("Verifier:" in finding for finding in report.findings)


def test_maximum_loop_termination(graph_deps) -> None:
    state = _run(
        graph_deps,
        "Find delayed webhook events for M999",
        max_iterations=1,
    )
    report = report_from(state)
    _assert_safe_trace(state)
    assert state["iteration"] == 1
    assert state["max_iterations"] == 1
    assert report.evidence_sufficient is False
    assert "writer" in _nodes(state)
    assert "refine" not in _nodes(state)
    assert "incident_risk" not in _nodes(state)
    assert any(event.decision == "insufficient" for event in state["trace"])
