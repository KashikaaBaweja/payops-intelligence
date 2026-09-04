"""Deterministic investigation evaluation harness. No LLM calls."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from payops_core.data.engine import make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.eval.dataset import CASES
from payops_core.eval.schema import CaseResult, EvalCase, EvalReport, MetricScore
from payops_core.graph.build import report_from, run_investigation
from payops_core.models.schemas import Hypothesis
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

_CORPUS = Path(__file__).resolve().parents[3] / "docs" / "corpus"
_SKIP_ACTIONS = {"skip", "timeout", "failed"}


def _bool_metric(name: str, passed: bool, detail: str = "", applicable: bool = True) -> MetricScore:
    return MetricScore(
        name=name,
        score=1.0 if passed else 0.0,
        detail=detail,
        applicable=applicable,
    )


def evaluate_case(case: EvalCase, retriever: DocumentRetriever, session: Session) -> CaseResult:
    from payops_core.agents.incident import IncidentRiskAgent

    def _run() -> object:
        return run_investigation(
            case.question,
            retriever=retriever,
            session=session,
            max_iterations=case.max_iterations,
        )

    if case.inject_hypothesis is None:
        state = _run()
    else:
        injected = case.inject_hypothesis

        def _incorrect(_self, evidence, _metrics, _question):
            return [
                Hypothesis(
                    cause=injected.cause,
                    supporting_evidence_ids=list(evidence.ids()[:1]),
                    confidence=injected.confidence,
                    category=injected.category,
                )
            ]

        with patch.object(IncidentRiskAgent, "propose", _incorrect):
            state = _run()

    report = report_from(state)
    plan = state.get("plan")
    planned = [task.task_type for task in plan.tasks] if plan is not None else []
    trace = state.get("trace") or []
    nodes = [event.node for event in trace]
    used = [
        event.decision
        for event in trace
        if event.node == "investigate" and event.action not in _SKIP_ACTIONS and event.decision
    ]
    evidence = state.get("evidence")
    items = list(evidence.items) if evidence is not None else []
    retrieved_docs = {item.doc_id for item in items if item.source == "doc" and item.doc_id}
    sources = {item.source for item in items}
    known_ids = {item.evidence_id for item in items}
    cited_ids = {ref.evidence_id for ref in report.evidence}
    metrics: list[MetricScore] = []

    missing_tools = [name for name in case.expected_tools if name not in planned]
    metrics.append(
        _bool_metric(
            "tool_selection",
            not missing_tools,
            "planned=" + ",".join(planned),
        )
    )
    forbidden_hit = [name for name in case.forbidden_tools if name in planned or name in used]
    metrics.append(
        _bool_metric(
            "unnecessary_tool_calls",
            not forbidden_hit,
            "forbidden=" + ",".join(forbidden_hit) if forbidden_hit else "none",
        )
    )
    if case.relevant_doc_ids:
        hit = bool(retrieved_docs & set(case.relevant_doc_ids))
        metrics.append(
            _bool_metric(
                "retrieval_relevance",
                hit,
                "docs=" + ",".join(sorted(x for x in retrieved_docs if x)),
            )
        )
    else:
        metrics.append(_bool_metric("retrieval_relevance", True, applicable=False))
    if case.required_sources:
        missing_sources = [name for name in case.required_sources if name not in sources]
        metrics.append(
            _bool_metric(
                "evidence_grounding",
                not missing_sources,
                "sources=" + ",".join(sorted(sources)),
            )
        )
    else:
        metrics.append(_bool_metric("evidence_grounding", True, applicable=False))
    metrics.append(
        _bool_metric(
            "citation_correctness",
            cited_ids <= known_ids,
            f"cited={len(cited_ids)} known={len(known_ids)}",
        )
    )
    metrics.append(
        _bool_metric(
            "investigation_completion",
            "writer" in nodes and report.executive_summary != "",
            "nodes=" + ",".join(nodes),
        )
    )
    if case.expect_unsupported:
        cause = report.likely_cause.cause.lower()
        injected_cause = (case.inject_hypothesis.cause if case.inject_hypothesis else "").lower()
        leaked = bool(injected_cause) and injected_cause in cause
        metrics.append(
            _bool_metric(
                "unsupported_claims",
                not leaked,
                f"cause={report.likely_cause.cause}",
            )
        )
    else:
        metrics.append(_bool_metric("unsupported_claims", True, applicable=False))
    maximum = int(state.get("max_iterations") or 1)
    iteration = int(state.get("iteration") or 0)
    metrics.append(
        _bool_metric(
            "loop_termination",
            iteration <= maximum,
            f"iteration={iteration} max={maximum}",
        )
    )
    if case.expect_refine is not None:
        metrics.append(
            _bool_metric(
                "refine_loop",
                ("refine" in nodes) is case.expect_refine,
                "refine=" + str("refine" in nodes),
            )
        )
    if case.expected_sufficient is not None:
        metrics.append(
            _bool_metric(
                "sufficiency",
                report.evidence_sufficient is case.expected_sufficient,
                f"sufficient={report.evidence_sufficient}",
            )
        )

    applicable = [item for item in metrics if item.applicable]
    passed = all(item.score == 1.0 for item in applicable)
    notes = [item.detail for item in applicable if item.score != 1.0 and item.detail]
    return CaseResult(
        case_id=case.id,
        category=case.category,
        question=case.question,
        expected_behavior=case.expected_behavior,
        passed=passed,
        metrics=metrics,
        planned_tools=planned,
        used_tools=used,
        iteration=iteration,
        evidence_sufficient=report.evidence_sufficient,
        notes=notes,
    )


def run_suite(
    cases: Sequence[EvalCase] | None = None,
    *,
    database_url: str | None = None,
) -> EvalReport:
    selected = list(cases or CASES)
    if database_url is None:
        from tempfile import mkdtemp

        database_url = f"sqlite:///{Path(mkdtemp()) / 'eval.db'}"
    seed(database_url, rng_seed=42)
    engine = make_engine(database_url)
    store, _count = ingest_corpus(_CORPUS, store=InMemoryVectorStore())
    retriever = DocumentRetriever(store)
    factory = session_factory(engine)
    results: list[CaseResult] = []
    with factory() as session:
        for case in selected:
            results.append(evaluate_case(case, retriever, session))
    passed = sum(1 for item in results if item.passed)
    metric_totals: dict[str, list[float]] = {}
    category_hits: dict[str, list[bool]] = {}
    for result in results:
        category_hits.setdefault(result.category, []).append(result.passed)
        for metric in result.metrics:
            if metric.applicable and metric.score is not None:
                metric_totals.setdefault(metric.name, []).append(metric.score)
    return EvalReport(
        case_count=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=(passed / len(results)) if results else 0.0,
        metric_means={
            name: (sum(values) / len(values) if values else 0.0)
            for name, values in metric_totals.items()
        },
        category_pass_rate={
            name: (sum(1 for item in values if item) / len(values) if values else 0.0)
            for name, values in category_hits.items()
        },
        cases=results,
    )


def render_markdown(report: EvalReport) -> str:
    lines = [
        "# PayOps evaluation report",
        "",
        f"- Cases: {report.case_count}",
        f"- Passed: {report.passed}",
        f"- Failed: {report.failed}",
        f"- Pass rate: {report.pass_rate:.0%}",
        "",
        "## Metric means",
        "",
    ]
    for name, value in sorted(report.metric_means.items()):
        lines.append(f"- `{name}`: {value:.2f}")
    lines.extend(["", "## Categories", ""])
    for name, value in sorted(report.category_pass_rate.items()):
        lines.append(f"- `{name}`: {value:.0%}")
    lines.extend(["", "## Cases", ""])
    for result in report.cases:
        mark = "pass" if result.passed else "FAIL"
        lines.append(f"- `{result.case_id}` {mark} — {result.expected_behavior}")
        if result.notes:
            lines.append(f"  - {'; '.join(result.notes)}")
    lines.append("")
    return "\n".join(lines)
