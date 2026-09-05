from datetime import datetime

from payops_core.agents.incident import _ids_for
from payops_core.agents.sufficiency import SufficiencyAgent
from payops_core.graph.nodes import _run_task, investigate_node
from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceItem,
    InvestigationPlan,
    MerchantHealthScore,
    MetricResult,
    Task,
    TimeWindow,
)
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

from apps.api.routers.investigations import _status_from_state
from apps.api.store import InvestigationStore, StoredInvestigation


def test_status_from_state_marks_timeout_and_error() -> None:
    assert _status_from_state({}) == ("completed", None)
    assert _status_from_state({"timed_out": True})[0] == "failed"
    assert _status_from_state({"error": "tool blew up"}) == ("failed", "tool blew up")


def test_evidence_ids_include_window() -> None:
    window = TimeWindow(start=datetime(2024, 6, 1), end=datetime(2024, 6, 8))
    metric = MetricResult(
        metric="failure_rate",
        value=0.2,
        window=window,
        operation="get_failure_rate",
        merchant_id="M102",
    )
    health = MerchantHealthScore(
        merchant_id="M102",
        window=window,
        score=70,
        band="degraded",
        factors=[],
        factor_values={"success_rate": 0.8},
    )
    other = MetricResult(
        metric="failure_rate",
        value=0.1,
        window=TimeWindow(start=datetime(2024, 6, 8), end=datetime(2024, 6, 15)),
        operation="get_failure_rate",
        merchant_id="M102",
    )
    assert metric.to_evidence().evidence_id != other.to_evidence().evidence_id
    assert "20240601" in metric.to_evidence().evidence_id
    assert "20240601" in health.to_evidence().evidence_id


def test_sufficiency_ignores_error_stubs() -> None:
    plan = InvestigationPlan(
        goal="score",
        merchant_id="M102",
        tasks=[
            Task(task_id="t1", task_type="score_risk", rationale="ml", merchant_id="M102"),
        ],
    )
    evidence = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="ml-error-classification-M102",
                source="ml",
                text_snippet="classifier unavailable",
                metadata={"error": "InsufficientTrainingData", "task": "classification"},
            )
        ]
    )
    verdict = SufficiencyAgent().evaluate(plan, evidence)
    assert verdict.sufficient is False
    assert verdict.missing


def test_incident_does_not_attach_unrelated_ids() -> None:
    evidence = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="doc-lifecycle",
                source="doc",
                text_snippet="Payment lifecycle has authorized, captured, settled.",
            )
        ]
    )
    assert _ids_for(evidence, ("GATEWAY_TIMEOUT", "timeout")) == []


def test_unknown_task_type_raises() -> None:
    class _Runtime:
        session = None
        retriever = DocumentRetriever(InMemoryVectorStore())

    task = Task.model_construct(
        task_id="x",
        task_type="not_a_real_task",
        rationale="invalid",
    )
    try:
        _run_task({"question": "why", "merchant_id": "M102"}, _Runtime(), task)
        raise AssertionError("expected unknown task type")
    except ValueError as exc:
        assert "unknown task type" in str(exc)


def test_investigate_continues_after_tool_failure() -> None:
    import payops_core.graph.nodes as nodes

    calls: list[str] = []

    def _fake(state, runtime, task):
        calls.append(task.task_id)
        if task.task_id == "a":
            raise RuntimeError("boom")
        return (
            [
                EvidenceItem(
                    evidence_id="metric-ok",
                    source="metric",
                    text_snippet="failure_rate=0.2",
                )
            ],
            [],
            "sql_gateway",
            task.query,
            None,
        )

    original = nodes._run_task
    nodes._run_task = _fake  # type: ignore[method-assign]
    try:

        class _Runtime:
            def expired(self) -> bool:
                return False

        result = investigate_node(
            {
                "question": "why",
                "pending_tasks": [
                    Task(task_id="a", task_type="query_metrics", rationale="first"),
                    Task(task_id="b", task_type="query_metrics", rationale="second"),
                ],
                "iteration": 0,
            },
            _Runtime(),
        )
    finally:
        nodes._run_task = original  # type: ignore[method-assign]
    assert calls == ["a", "b"]
    assert result["completed_task_ids"] == ["b"]
    assert any(item.evidence_id == "metric-ok" for item in result["evidence"].items)
    assert any(event.action == "failed" for event in result["trace"])


def test_index_evidence_does_not_clobber_investigation(tmp_path) -> None:
    from payops_core.data.engine import create_schema, make_engine, session_factory

    engine = make_engine(f"sqlite:///{tmp_path / 'store.db'}")
    create_schema(engine)
    session = session_factory(engine)()
    store = InvestigationStore(session)
    item = EvidenceItem(
        evidence_id="metric-get_failure_rate-M102-20240601-20240608",
        source="metric",
        text_snippet="failure_rate=0.4",
    )
    store.put(
        StoredInvestigation(
            investigation_id="inv-1",
            question="why",
            status="completed",
            report=None,
            trace=[],
            evidence=[item],
        )
    )
    store.index_evidence(
        [
            EvidenceItem(
                evidence_id=item.evidence_id,
                source="metric",
                text_snippet="failure_rate=0.99",
            )
        ]
    )
    stored = store.get_evidence(item.evidence_id)
    assert stored is not None
    assert stored.text_snippet == "failure_rate=0.4"
    session.close()
