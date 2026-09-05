"""LangGraph investigation FSM.

Product agents map to existing nodes and catalog tools — not one giant prompt:

1. Orchestrator — this compiled graph (planner → investigate → sufficiency ⇄ refine → …)
2. Research — ResearcherAgent formulates queries and scores relevance
3. Retrieval — RetrievalAgent executes search_docs
4. Data Analyst — DataAnalystAgent / SqlToolGateway
5. ML — MLAgent / score_risk or score_regression (never mixed metrics)
6. Transaction Integrity — TransactionIntegrityAgent / validate_integrity
7. Critic/Verifier — VerifierAgent then CriticAgent
8. Report Writer — WriterAgent
"""

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
    route_after_critic,
    route_after_sufficiency,
    route_after_verifier,
    sufficiency_node,
    verifier_node,
    writer_node,
)
from payops_core.graph.runtime import GraphRuntime
from payops_core.graph.state import InvestigationState
from payops_core.models.schemas import EvidenceBundle, IncidentReport
from payops_core.query_language import (
    detect_query_language,
    resolve_response_language,
    retrieval_query,
)
from payops_core.rag.retriever import DocumentRetriever


def initial_state(
    question: str,
    max_iterations: int,
    merchant_id: str | None = None,
    input_method: str = "text",
    language: str = "auto",
) -> InvestigationState:
    return {
        "question": question,
        "input_method": input_method if input_method == "voice" else "text",
        "query_language": detect_query_language(question),
        "response_language": resolve_response_language(question, language),
        "retrieval_query": retrieval_query(question),
        "merchant_id": merchant_id,
        "time_window": None,
        "plan": None,
        "evidence": EvidenceBundle(),
        "metrics": [],
        "hypotheses": [],
        "sufficiency": None,
        "verified_claims": [],
        "verification": None,
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
        "retrieval": None,
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
    graph.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "refine": "refine",
            "writer": "writer",
        },
    )
    graph.add_edge("writer", "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "writer": "writer",
            "end": END,
        },
    )
    return graph.compile()


def run_investigation(
    question: str,
    *,
    retriever: DocumentRetriever,
    session: Session,
    max_iterations: int | None = None,
    timeout_seconds: float | None = None,
    merchant_id: str | None = None,
    input_method: str = "text",
    language: str = "auto",
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
        initial_state(
            question,
            max_iterations or settings.max_iterations,
            merchant_id=merchant_id,
            input_method=input_method,
            language=language,
        )
    )
    return result  # type: ignore[return-value]


def report_from(state: InvestigationState) -> IncidentReport:
    report = state.get("report")
    if report is None:
        raise RuntimeError("investigation did not produce a report")
    return report
