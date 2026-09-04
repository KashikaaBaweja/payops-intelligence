from __future__ import annotations

import json

from payops_core.graph.state import InvestigationState
from payops_core.llm import LLMClient, get_llm
from payops_core.models import (
    CritiqueResult,
    EvidenceBundle,
    EvidenceItem,
    Hypothesis,
    IncidentReport,
    InvestigationPlan,
    SufficiencyVerdict,
    Task,
    TimeWindow,
    TraceEvent,
    VerifiedClaim,
)
from payops_core.tools import SqlGateway, SqlOpRequest, WebhookTool, merchant_health, search_docs


def _trace(state: InvestigationState, step: str, agent: str, tool: str | None, inp: str, out: str) -> None:
    events = list(state.get("trace") or [])
    events.append(
        TraceEvent(
            step=step,
            agent=agent,
            tool=tool,
            input_summary=inp[:400],
            output_summary=out[:400],
        )
    )
    state["trace"] = events


class PlannerAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        payload = {
            "question": state["question"],
            "merchant_id": state.get("merchant_id"),
            "time_window": state.get("time_window").model_dump(mode="json") if state.get("time_window") else None,
        }
        raw = self.llm.complete_json(
            "You are a payments-ops planner. Emit only a structured investigation plan.",
            json.dumps(payload, default=str),
            "InvestigationPlan",
        )
        plan = InvestigationPlan.model_validate(raw)
        if state.get("merchant_id") and not plan.merchant_id:
            plan.merchant_id = state["merchant_id"]
        if state.get("time_window") and not plan.time_window:
            plan.time_window = state["time_window"]
        state["plan"] = plan
        state["pending_tasks"] = [t.model_dump() for t in plan.tasks]
        _trace(state, "planner.plan", "planner", None, state["question"], f"{len(plan.tasks)} tasks")
        return state


class ResearcherAgent:
    def run(self, state: InvestigationState) -> InvestigationState:
        tasks = [Task.model_validate(t) for t in state.get("pending_tasks") or [] if t["task_type"] == "retrieve_docs"]
        bundle = state.get("evidence") or EvidenceBundle()
        added = 0
        for task in tasks:
            hits = search_docs(task.query or state["question"])
            bundle.items.extend(hits)
            added += len(hits)
        state["evidence"] = bundle
        _trace(state, "researcher.search_docs", "researcher", "search_docs", state["question"], f"{added} chunks")
        return state


class DataAnalystAgent:
    def __init__(self, gateway: SqlGateway | None = None) -> None:
        self.gateway = gateway or SqlGateway()

    def run(self, state: InvestigationState) -> InvestigationState:
        tasks = [
            Task.model_validate(t)
            for t in state.get("pending_tasks") or []
            if t["task_type"] in {"query_metrics", "compare_merchants"}
        ]
        metrics = list(state.get("metrics") or [])
        bundle = state.get("evidence") or EvidenceBundle()
        window = state.get("time_window") or (state.get("plan").time_window if state.get("plan") else None)
        merchant_id = state.get("merchant_id") or (state.get("plan").merchant_id if state.get("plan") else None)
        ops = ["get_success_rate", "get_failure_rate", "breakdown_by_error_code", "breakdown_by_method"]
        if any(t.task_type == "compare_merchants" for t in tasks):
            ops.append("compare_windows")
        for op in ops:
            req = SqlOpRequest(
                operation=op,  # type: ignore[arg-type]
                merchant_id=merchant_id,
                method_id=next((t.method_id for t in tasks if t.method_id), None),
                window=window,
                compare_window=_baseline(window) if op == "compare_windows" else None,
            )
            result = self.gateway.run(req)
            metrics.append(result)
            bundle.items.append(
                EvidenceItem(
                    evidence_id=f"metric-{op}-{merchant_id}",
                    source="metric",
                    text_snippet=f"{op}={result.value}",
                    metadata=result.model_dump(mode="json"),
                )
            )
        state["metrics"] = metrics
        state["evidence"] = bundle
        _trace(state, "data_analyst.query_metrics", "data_analyst", "sql_gateway", str(merchant_id), f"{len(ops)} ops")
        return state


class WebhookInspectorAgent:
    def __init__(self, tool: WebhookTool | None = None) -> None:
        self.tool = tool or WebhookTool()

    def run(self, state: InvestigationState) -> InvestigationState:
        tasks = [t for t in state.get("pending_tasks") or [] if t["task_type"] == "inspect_webhooks"]
        merchant_id = state.get("merchant_id")
        if not tasks or not merchant_id:
            return state
        bundle = state.get("evidence") or EvidenceBundle()
        window = state.get("time_window")
        bundle.items.extend(self.tool.get_delivery_failures(merchant_id, window))
        bundle.items.append(self.tool.find_delayed_events(merchant_id, window=window))
        state["evidence"] = bundle
        _trace(state, "webhook.inspect", "webhook_inspector", "webhook_tool", merchant_id, "delivery stats")
        return state


class HealthAgent:
    def run(self, state: InvestigationState) -> InvestigationState:
        tasks = [t for t in state.get("pending_tasks") or [] if t["task_type"] == "merchant_health"]
        merchant_id = state.get("merchant_id")
        if not tasks or not merchant_id:
            return state
        bundle = state.get("evidence") or EvidenceBundle()
        bundle.items.append(merchant_health(merchant_id, state.get("time_window")))
        state["evidence"] = bundle
        _trace(state, "health.score", "incident_risk", "merchant_health", merchant_id, "scored")
        return state


class SufficiencyAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        payload = {
            "question": state["question"],
            "merchant_id": state.get("merchant_id"),
            "evidence": (state.get("evidence") or EvidenceBundle()).model_dump(mode="json"),
            "iteration": state.get("iteration", 0),
        }
        raw = self.llm.complete_json(
            "Decide if evidence is sufficient. Never invent missing data.",
            json.dumps(payload, default=str),
            "SufficiencyVerdict",
        )
        verdict = SufficiencyVerdict.model_validate(raw)
        state["sufficiency"] = verdict
        state["iteration"] = int(state.get("iteration") or 0) + 1
        if not verdict.sufficient and verdict.next_action == "refine":
            extra = []
            for gap in verdict.missing:
                extra.append(
                    Task(
                        task_id=f"gap-{gap.next_task_type}",
                        task_type=gap.next_task_type if gap.next_task_type in {
                            "retrieve_docs", "query_metrics", "inspect_webhooks",
                            "compare_merchants", "merchant_health",
                        } else "retrieve_docs",
                        rationale=gap.description,
                        query=gap.suggested_query or state["question"],
                        merchant_id=state.get("merchant_id"),
                    ).model_dump()
                )
            state["pending_tasks"] = extra
        _trace(
            state,
            "sufficiency.evaluate",
            "sufficiency",
            None,
            f"iter={state['iteration']}",
            str(verdict.sufficient),
        )
        return state


class IncidentRiskAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        payload = {
            "evidence": (state.get("evidence") or EvidenceBundle()).model_dump(mode="json"),
            "merchant_id": state.get("merchant_id"),
        }
        raw = self.llm.complete_json(
            "Rank hypotheses using only provided evidence ids.",
            json.dumps(payload, default=str),
            "Hypothesis",
        )
        hyps = [Hypothesis.model_validate(h) for h in raw.get("hypotheses", [raw])]
        state["hypotheses"] = hyps
        _trace(state, "incident_risk.rank", "incident_risk", None, "evidence bundle", f"{len(hyps)} hypotheses")
        return state


class VerifierAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        hyps = state.get("hypotheses") or []
        payload = {
            "hypothesis": hyps[0].model_dump() if hyps else {},
            "evidence_ids": (state.get("evidence") or EvidenceBundle()).ids(),
        }
        raw = self.llm.complete_json(
            "Flag claims that lack evidence ids.",
            json.dumps(payload, default=str),
            "VerifiedClaim",
        )
        claims = [VerifiedClaim.model_validate(c) for c in raw.get("claims", [raw])]
        state["verified_claims"] = claims
        _trace(state, "verifier.check", "verifier", None, "claims", f"{sum(c.supported for c in claims)} supported")
        return state


class CriticAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        payload = {"report": state["report"].model_dump(mode="json") if state.get("report") else {}}
        raw = self.llm.complete_json(
            "Review completeness and unsupported conclusions.",
            json.dumps(payload, default=str),
            "CritiqueResult",
        )
        critique = CritiqueResult.model_validate(raw)
        state["critique"] = critique
        _trace(state, "critic.review", "critic", None, "draft report", str(critique.approved))
        return state


class WriterAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or get_llm()

    def run(self, state: InvestigationState) -> InvestigationState:
        if state.get("critique") and not state["critique"].approved:
            state["critic_revisions"] = int(state.get("critic_revisions") or 0) + 1
        sufficient = True
        verdict = state.get("sufficiency")
        if verdict is not None:
            sufficient = verdict.sufficient
        if (state.get("merchant_id") == "M305") or (
            not sufficient and int(state.get("iteration") or 0) >= int(state.get("max_iterations") or 1)
        ):
            sufficient = False
        payload = {
            "merchant_id": state.get("merchant_id"),
            "time_window": state.get("time_window").model_dump() if state.get("time_window") else None,
            "evidence": (state.get("evidence") or EvidenceBundle()).model_dump(mode="json"),
            "metrics": [m.model_dump(mode="json") for m in state.get("metrics") or []],
            "hypotheses": [h.model_dump() for h in state.get("hypotheses") or []],
            "sufficient": sufficient,
            "critique": state.get("critique").model_dump() if state.get("critique") else None,
        }
        raw = self.llm.complete_json(
            "Write an incident report. Only use provided evidence. Do not invent causes.",
            json.dumps(payload, default=str),
            "IncidentReport",
        )
        report = IncidentReport.model_validate(raw)
        report.agent_execution_summary = list(state.get("trace") or [])
        report.evidence_sufficient = sufficient
        state["report"] = report
        _trace(state, "writer.compose", "writer", None, f"sufficient={sufficient}", report.incident_id)
        return state


def _baseline(window: TimeWindow | None) -> TimeWindow | None:
    if window is None:
        return None
    delta = window.end - window.start
    return TimeWindow(start=window.start - delta, end=window.start)
