from __future__ import annotations

from payops_core.agents.analyst import DataAnalystAgent
from payops_core.agents.critic import CriticAgent
from payops_core.agents.incident import IncidentRiskAgent
from payops_core.agents.integrity import TransactionIntegrityAgent
from payops_core.agents.ml_agent import MLAgent
from payops_core.agents.planner import DEFAULT_WINDOW, PlannerAgent
from payops_core.agents.researcher import ResearcherAgent
from payops_core.agents.sufficiency import SufficiencyAgent, task_from_gap
from payops_core.agents.verifier import VerifierAgent
from payops_core.agents.webhook_inspector import WebhookInspectorAgent
from payops_core.agents.writer import WriterAgent
from payops_core.config import get_settings
from payops_core.graph.runtime import GraphRuntime
from payops_core.graph.state import InvestigationState
from payops_core.graph.trace import safe_trace
from payops_core.models.schemas import (
    AgenticRagResult,
    EvidenceBundle,
    EvidenceItem,
    MetricResult,
    RetrievalSummary,
    Task,
    TraceEvent,
)
from payops_core.tools.merchant_health import score_merchant


def planner_node(state: InvestigationState) -> dict:
    question = state["question"]
    input_method = state.get("input_method") or "text"
    query_language = state.get("query_language") or "en"
    retrieval = state.get("retrieval_query")
    plan = PlannerAgent().plan(question, merchant_id=state.get("merchant_id"))
    traces = [
        safe_trace(
            node="planner",
            action="accept_query",
            search_query=question,
            decision=input_method if input_method == "voice" else "text",
        ),
        safe_trace(
            node="planner",
            action="query_language",
            search_query=question,
            decision=query_language,
        ),
    ]
    if retrieval:
        traces.append(
            safe_trace(
                node="planner",
                action="retrieval_query",
                search_query=retrieval,
                decision="glossary_expand",
            )
        )
    traces.append(
        safe_trace(
            node="planner",
            action="plan",
            search_query=question,
            decision=",".join(task.task_type for task in plan.tasks) or "none",
        )
    )
    return {
        "plan": plan,
        "merchant_id": plan.merchant_id,
        "time_window": plan.time_window,
        "pending_tasks": list(plan.tasks),
        "evidence": state.get("evidence") or EvidenceBundle(),
        "metrics": state.get("metrics") or [],
        "trace": traces,
    }


def investigate_node(state: InvestigationState, runtime: GraphRuntime) -> dict:
    iteration = int(state.get("iteration") or 0) + 1
    pending = list(state.get("pending_tasks") or [])
    if runtime.expired():
        return {
            "iteration": iteration,
            "timed_out": True,
            "pending_tasks": [],
            "trace": [safe_trace(node="investigate", action="timeout", decision="timeout")],
        }
    if not pending:
        return {
            "iteration": iteration,
            "trace": [safe_trace(node="investigate", action="skip", decision="no_pending_tasks")],
        }
    evidence = state.get("evidence") or EvidenceBundle()
    combined_metrics = list(state.get("metrics") or [])
    retrieval = state.get("retrieval")
    traces = []
    completed: list[str] = []
    failures: list[str] = []
    for index, task in enumerate(pending):
        if runtime.expired():
            return {
                "iteration": iteration,
                "timed_out": True,
                "pending_tasks": pending[index:],
                "completed_task_ids": completed,
                "evidence": evidence,
                "metrics": combined_metrics,
                "trace": traces
                + [safe_trace(node="investigate", action="timeout", decision="timeout")],
            }
        try:
            items, metrics, tool, query, rag = _run_task(state, runtime, task)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{task.task_type}:{type(exc).__name__}: {exc}"[:180])
            traces.append(
                safe_trace(
                    node="investigate",
                    action="failed",
                    tool=task.task_type,
                    search_query=task.query,
                    decision="failed",
                )
            )
            continue
        evidence = _merge_evidence(evidence, items)
        combined_metrics = combined_metrics + metrics
        completed.append(task.task_id)
        if rag is not None:
            traces.extend(_rag_traces(rag))
            retrieval = _retrieval_summary(rag)
        traces.append(
            safe_trace(
                node="investigate",
                action="run_task",
                tool=tool,
                search_query=query,
                evidence_ids=[item.evidence_id for item in items],
                decision=task.task_type,
            )
        )
    return {
        "iteration": iteration,
        "pending_tasks": [],
        "completed_task_ids": completed,
        "evidence": evidence,
        "metrics": combined_metrics,
        "retrieval": retrieval,
        "error": ("; ".join(failures) if failures and not completed else state.get("error")),
        "trace": traces,
    }


def aggregate_node(state: InvestigationState) -> dict:
    evidence = state.get("evidence") or EvidenceBundle()
    return {
        "evidence": evidence,
        "trace": [
            safe_trace(
                node="aggregate",
                action="merge",
                evidence_ids=evidence.ids(),
                decision=f"count={len(evidence.items)}",
            )
        ],
    }


def sufficiency_node(state: InvestigationState) -> dict:
    verdict = SufficiencyAgent().evaluate(
        state.get("plan"),
        state.get("evidence") or EvidenceBundle(),
    )
    return {
        "sufficiency": verdict,
        "trace": [
            safe_trace(
                node="sufficiency",
                action="evaluate",
                evidence_ids=(state.get("evidence") or EvidenceBundle()).ids(),
                decision="sufficient" if verdict.sufficient else "insufficient",
            )
        ],
    }


def refine_node(state: InvestigationState) -> dict:
    pending = list(state.get("pending_tasks") or [])
    if pending:
        return {
            "trace": [
                safe_trace(
                    node="refine",
                    action="keep_pending",
                    decision=",".join(task.task_type for task in pending),
                )
            ]
        }
    gaps = []
    verdict = state.get("sufficiency")
    if verdict is not None:
        gaps.extend(verdict.missing)
    verification = state.get("verification")
    if verification is not None:
        gaps.extend(verification.gaps)
    extra = [task_from_gap(gap, index) for index, gap in enumerate(gaps)]
    return {
        "pending_tasks": extra,
        "trace": [
            safe_trace(
                node="refine",
                action="queue_gaps",
                decision=",".join(task.task_type for task in extra) or "none",
            )
        ],
    }


def incident_node(state: InvestigationState) -> dict:
    hypotheses = IncidentRiskAgent().propose(
        state.get("evidence") or EvidenceBundle(),
        state.get("metrics") or [],
        state["question"],
    )
    return {
        "hypotheses": hypotheses,
        "trace": [
            safe_trace(
                node="incident_risk",
                action="propose",
                evidence_ids=hypotheses[0].supporting_evidence_ids if hypotheses else [],
                decision=hypotheses[0].category if hypotheses else "none",
            )
        ],
    }


def verifier_node(state: InvestigationState) -> dict:
    result = VerifierAgent().verify(
        state.get("hypotheses") or [],
        state.get("evidence") or EvidenceBundle(),
    )
    decision = "investigate" if result.needs_more_evidence else result.status
    return {
        "verified_claims": result.claims,
        "verification": result,
        "trace": [
            safe_trace(
                node="verifier",
                action="verify",
                evidence_ids=[item for claim in result.claims for item in claim.evidence_ids],
                decision=decision,
                verification_status=result.status,
            )
        ],
    }


def critic_node(state: InvestigationState) -> dict:
    critique = CriticAgent().review(
        state["question"],
        state.get("plan"),
        state.get("sufficiency"),
        state.get("verified_claims") or [],
        state.get("report"),
    )
    return {
        "critique": critique,
        "trace": [
            safe_trace(
                node="critic",
                action="review",
                decision="approved" if critique.approved else "revise",
                verification_status="supported" if critique.approved else "unsupported",
            )
        ],
    }


def writer_node(state: InvestigationState) -> dict:
    revisions = int(state.get("critic_revisions") or 0)
    if state.get("critique") is not None:
        revisions += 1
    report = WriterAgent().write(
        question=state["question"],
        merchant_id=state.get("merchant_id"),
        window=state.get("time_window"),
        evidence=state.get("evidence") or EvidenceBundle(),
        metrics=state.get("metrics") or [],
        hypotheses=state.get("hypotheses") or [],
        sufficiency=state.get("sufficiency"),
        claims=state.get("verified_claims") or [],
        critique=state.get("critique"),
        trace=list(state.get("trace") or []),
        error=state.get("error"),
        timed_out=bool(state.get("timed_out")),
        retrieval=state.get("retrieval"),
        query_language=state.get("query_language") or "en",
        response_language=state.get("response_language") or "en",
        retrieval_query=state.get("retrieval_query"),
    )
    return {
        "report": report,
        "critic_revisions": revisions,
        "trace": [
            safe_trace(
                node="writer",
                action="write",
                evidence_ids=report.likely_cause.supporting_evidence_ids,
                decision="complete" if report.evidence_sufficient else "insufficient",
                verification_status="supported" if report.evidence_sufficient else "unsupported",
            )
        ],
    }


def route_after_sufficiency(state: InvestigationState) -> str:
    if state.get("timed_out") or state.get("error"):
        return "writer"
    verdict = state.get("sufficiency")
    if verdict is not None and verdict.sufficient:
        return "incident_risk"
    iteration = int(state.get("iteration") or 0)
    maximum = int(state.get("max_iterations") or 1)
    if iteration >= maximum:
        return "writer"
    return "refine"


def route_after_verifier(state: InvestigationState) -> str:
    if state.get("timed_out") or state.get("error"):
        return "writer"
    verification = state.get("verification")
    iteration = int(state.get("iteration") or 0)
    maximum = int(state.get("max_iterations") or 1)
    if verification is not None and verification.needs_more_evidence and iteration < maximum:
        return "refine"
    return "writer"


def route_after_critic(state: InvestigationState) -> str:
    critique = state.get("critique")
    revisions = int(state.get("critic_revisions") or 0)
    if critique is not None and not critique.approved and revisions < 1:
        return "writer"
    return "end"


def _run_task(
    state: InvestigationState,
    runtime: GraphRuntime,
    task: Task,
) -> tuple[list[EvidenceItem], list[MetricResult], str, str | None, AgenticRagResult | None]:
    question = state["question"]
    merchant_id = task.merchant_id or state.get("merchant_id")
    window = state.get("time_window") or DEFAULT_WINDOW
    if task.task_type == "retrieve_docs":
        result = ResearcherAgent(
            runtime.retriever,
            max_iterations=get_settings().rag_max_iterations,
        ).research(task.query or question, task=task)
        query = result.queries[0].query if result.queries else task.query
        return result.evidence.items, [], "search_docs", query, result.rag
    if task.task_type == "merchant_health":
        if not merchant_id:
            raise ValueError("merchant_health requires a merchant_id")
        scored = score_merchant(runtime.session, merchant_id, window)
        return [scored.to_evidence()], [], "merchant_health", task.query, None
    if task.task_type == "score_risk":
        if not merchant_id:
            raise ValueError("score_risk requires a merchant_id")
        return (
            MLAgent().run_classification(runtime.session, merchant_id, window).items,
            [],
            "ml_risk",
            task.query,
            None,
        )
    if task.task_type == "score_regression":
        if not merchant_id:
            raise ValueError("score_regression requires a merchant_id")
        return (
            MLAgent().run_regression(runtime.session, merchant_id, window).items,
            [],
            "ml_regression",
            task.query,
            None,
        )
    if task.task_type == "validate_integrity":
        result = TransactionIntegrityAgent(runtime.session).inspect(
            task.query or question,
            window=window,
            merchant_id=merchant_id,
            task=task,
        )
        return result.evidence.items, [], "validate_integrity", task.query, None
    if task.task_type in {"query_metrics", "compare_merchants"}:
        result = DataAnalystAgent(runtime.session).analyze(
            task.query or question,
            window=window,
            merchant_id=merchant_id,
            method_id=task.method_id,
            task=task,
        )
        items = [metric.to_evidence() for metric in result.metrics]
        tool = result.operations[0] if result.operations else "sql_gateway"
        return items, result.metrics, tool, task.query, None
    if task.task_type != "inspect_webhooks":
        raise ValueError(f"unknown task type: {task.task_type}")
    result = WebhookInspectorAgent(runtime.session).inspect(
        task.query or question,
        window=window,
        merchant_id=merchant_id,
        task=task,
    )
    tool = result.operations[0] if result.operations else "webhook_gateway"
    return result.evidence.items, [], tool, task.query, None


def _rag_traces(rag: AgenticRagResult) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for index, step in enumerate(rag.rounds):
        events.append(
            safe_trace(
                node="investigate",
                action="rag_search",
                tool="search_docs",
                search_query=step.query,
                evidence_ids=step.evidence_ids,
                decision=f"search_{step.search_index}:{step.decision}",
            )
        )
        nxt = rag.rounds[index + 1] if index + 1 < len(rag.rounds) else None
        if nxt is not None:
            events.append(
                safe_trace(
                    node="investigate",
                    action="rag_rewrite",
                    tool="search_docs",
                    search_query=nxt.query,
                    decision=nxt.rewrite_reason or "query rewritten",
                )
            )
    events.append(
        safe_trace(
            node="investigate",
            action="rag_answer",
            tool="search_docs",
            evidence_ids=[item.evidence_id for item in rag.citations],
            decision="grounded" if rag.sources_verified and rag.sufficient else "insufficient",
        )
    )
    return events


def _retrieval_summary(rag: AgenticRagResult) -> RetrievalSummary:
    return RetrievalSummary(
        iterations=rag.iterations,
        max_iterations=rag.max_iterations,
        latency_ms=rag.latency_ms,
        sufficient=rag.sufficient,
        conflicting=rag.conflicting,
        conflict_note=rag.conflict_note,
        grounded_excerpt=rag.grounded_excerpt,
        citations=rag.citations,
        rounds=rag.rounds,
    )


def _merge_evidence(bundle: EvidenceBundle, items: list[EvidenceItem]) -> EvidenceBundle:
    known = {item.evidence_id: item for item in bundle.items}
    for item in items:
        known[item.evidence_id] = item
    return EvidenceBundle(items=list(known.values()))
