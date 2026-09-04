from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from payops_core.config import get_settings
from payops_core.graph.nodes import (
    aggregate_node,
    critic_node,
    incident_node,
    investigate_node,
    planner_node,
    refine_node,
    route_after_sufficiency,
    sufficiency_node,
    verifier_node,
    writer_node,
)
from payops_core.graph.runtime import GraphRuntime
from payops_core.graph.state import InvestigationState
from payops_core.models.schemas import EvidenceBundle, IncidentReport
from payops_core.rag.retriever import DocumentRetriever


def initial_state(question: str, max_iterations: int) -> InvestigationState:
    return {
        "question": question,
        "merchant_id": None,
        "time_window": None,
        "plan": None,
        "evidence": EvidenceBundle(),
        "metrics": [],
        "hypotheses": [],
        "sufficiency": None,
        "verified_claims": [],
        "critique": None,
        "report": None,
        "trace": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "critic_revisions": 0,
        "pending_tasks": [],
        "completed_task_ids": [],
        "error": None,
        "timed_out": False,
    }


def build_investigation_graph(runtime: GraphRuntime):
    graph = StateGraph(InvestigationState)
    graph.add_node("planner", planner_node)
    graph.add_node("investigate", lambda state: investigate_node(state, runtime))
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("sufficiency", sufficiency_node)
    graph.add_node("refine", refine_node)
    graph.add_node("incident_risk", incident_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("critic", critic_node)
    graph.add_node("writer", writer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "investigate")
    graph.add_edge("investigate", "aggregate")
    graph.add_edge("aggregate", "sufficiency")
    graph.add_conditional_edges(
        "sufficiency",
        route_after_sufficiency,
        {
            "refine": "refine",
            "incident_risk": "incident_risk",
            "writer": "writer",
        },
    )
    graph.add_edge("refine", "investigate")
    graph.add_edge("incident_risk", "verifier")
    graph.add_edge("verifier", "critic")
    graph.add_edge("critic", "writer")
    graph.add_edge("writer", END)
    return graph.compile()


def run_investigation(
    question: str,
    *,
    retriever: DocumentRetriever,
    session: Session,
    max_iterations: int | None = None,
    timeout_seconds: float | None = None,
) -> InvestigationState:
    settings = get_settings()
    runtime = GraphRuntime(
        retriever=retriever,
        session=session,
        timeout_seconds=timeout_seconds or settings.graph_timeout_seconds,
        started_at=time.monotonic(),
    )
    graph = build_investigation_graph(runtime)
    result = graph.invoke(
        initial_state(question, max_iterations or settings.max_iterations)
    )
    return result  # type: ignore[return-value]


def report_from(state: InvestigationState) -> IncidentReport:
    report = state.get("report")
    if report is None:
        raise RuntimeError("investigation did not produce a report")
    return report
