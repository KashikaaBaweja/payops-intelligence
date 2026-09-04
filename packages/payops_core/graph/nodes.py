from __future__ import annotations

from payops_core.agents.analyst import DataAnalystAgent
from payops_core.agents.critic import CriticAgent
from payops_core.agents.incident import IncidentRiskAgent
from payops_core.agents.planner import DEFAULT_WINDOW, PlannerAgent
from payops_core.agents.researcher import ResearcherAgent
from payops_core.agents.sufficiency import SufficiencyAgent, task_from_gap
from payops_core.agents.verifier import VerifierAgent
from payops_core.agents.webhook_inspector import WebhookInspectorAgent
from payops_core.agents.writer import WriterAgent
from payops_core.graph.runtime import GraphRuntime
from payops_core.graph.state import InvestigationState
from payops_core.graph.trace import safe_trace
from payops_core.models.schemas import EvidenceBundle, EvidenceItem, MetricResult, Task


def planner_node(state: InvestigationState) -> dict:
    question = state["question"]
    plan = PlannerAgent().plan(question)
    return {
        "plan": plan,
        "merchant_id": plan.merchant_id,
        "time_window": plan.time_window,
        "pending_tasks": list(plan.tasks),
        "evidence": state.get("evidence") or EvidenceBundle(),
        "metrics": state.get("metrics") or [],
        "trace": [
            safe_trace(
                node="planner",
                action="plan",
                search_query=question,
                decision=",".join(task.task_type for task in plan.tasks) or "none",
            )
        ],
    }


def investigate_node(state: InvestigationState, runtime: GraphRuntime) -> dict:
    iteration = int(state.get("iteration") or 0) + 1
    pending = list(state.get("pending_tasks") or [])
    if runtime.expired():
        return {
            "iteration": iteration,
            "timed_out": True,
            "pending_tasks": [],
            "trace": [
                safe_trace(node="investigate", action="timeout", decision="timeout")
            ],
        }
    if not pending:
        return {
            "iteration": iteration,
            "trace": [
                safe_trace(node="investigate", action="skip", decision="no_pending_tasks")
            ],
        }
    task = pending[0]
    remaining = pending[1:]
    try:
        items, metrics, tool, query = _run_task(state, runtime, task)
    except Exception as exc:  # noqa: BLE001
        return {
            "iteration": iteration,
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "pending_tasks": remaining,
            "completed_task_ids": [task.task_id],
            "trace": [
                safe_trace(
                    node="investigate",
                    action="failed",
                    tool=task.task_type,
                    search_query=task.query,
                    decision="failed",
                )
            ],
        }
    evidence = _merge_evidence(state.get("evidence") or EvidenceBundle(), items)
    combined_metrics = list(state.get("metrics") or []) + metrics
    return {
        "iteration": iteration,
        "pending_tasks": remaining,
        "completed_task_ids": [task.task_id],
        "evidence": evidence,
        "metrics": combined_metrics,
        "trace": [
            safe_trace(
                node="investigate",
                action="run_task",
                tool=tool,
                search_query=query,
                evidence_ids=[item.evidence_id for item in items],
                decision=task.task_type,
            )
        ],
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
    if (
        verification is not None
        and verification.needs_more_evidence
        and iteration < maximum
    ):
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
) -> tuple[list[EvidenceItem], list[MetricResult], str, str | None]:
    question = state["question"]
    merchant_id = task.merchant_id or state.get("merchant_id")
    window = state.get("time_window") or DEFAULT_WINDOW
    if task.task_type == "retrieve_docs":
        result = ResearcherAgent(runtime.retriever).research(task.query or question, task=task)
        query = result.queries[0].query if result.queries else task.query
        return result.evidence.items, [], "search_docs", query
    if task.task_type in {"query_metrics", "compare_merchants", "merchant_health"}:
        result = DataAnalystAgent(runtime.session).analyze(
            task.query or question,
            window=window,
            merchant_id=merchant_id,
            method_id=task.method_id,
            task=task if task.task_type == "query_metrics" else None,
        )
        items = [metric.to_evidence() for metric in result.metrics]
        tool = result.operations[0] if result.operations else "sql_gateway"
        return items, result.metrics, tool, task.query
    result = WebhookInspectorAgent(runtime.session).inspect(
        task.query or question,
        window=window,
        merchant_id=merchant_id,
        task=task if task.task_type == "inspect_webhooks" else None,
    )
    tool = result.operations[0] if result.operations else "webhook_gateway"
    return result.evidence.items, [], tool, task.query


def _merge_evidence(bundle: EvidenceBundle, items: list[EvidenceItem]) -> EvidenceBundle:
    known = {item.evidence_id: item for item in bundle.items}
    for item in items:
        known[item.evidence_id] = item
    return EvidenceBundle(items=list(known.values()))
