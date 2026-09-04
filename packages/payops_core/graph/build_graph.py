from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from payops_core.config import get_settings
from payops_core.graph.nodes import (
    CriticAgent,
    DataAnalystAgent,
    HealthAgent,
    IncidentRiskAgent,
    PlannerAgent,
    ResearcherAgent,
    SufficiencyAgent,
    VerifierAgent,
    WebhookInspectorAgent,
    WriterAgent,
)
from payops_core.graph.state import InvestigationState
from payops_core.models import EvidenceBundle, TimeWindow


def _route_after_sufficiency(state: InvestigationState) -> str:
    verdict = state.get("sufficiency")
    iteration = int(state.get("iteration") or 0)
    max_iterations = int(state.get("max_iterations") or get_settings().max_iterations)
    if verdict and not verdict.sufficient and iteration < max_iterations and verdict.next_action == "refine":
        return "dispatch"
    if verdict and not verdict.sufficient:
        return "writer"
    return "incident_risk"


def _route_after_critic(state: InvestigationState) -> str:
    critique = state.get("critique")
    revisions = int(state.get("critic_revisions") or 0)
    max_rev = get_settings().max_critic_revisions
    if critique and not critique.approved and revisions < max_rev:
        return "writer"
    return "end"


def build_graph(llm=None, gateway=None):
    planner = PlannerAgent(llm)
    researcher = ResearcherAgent()
    analyst = DataAnalystAgent(gateway)
    webhooks = WebhookInspectorAgent()
    health = HealthAgent()
    sufficiency = SufficiencyAgent(llm)
    incident = IncidentRiskAgent(llm)
    verifier = VerifierAgent(llm)
    critic = CriticAgent(llm)
    writer = WriterAgent(llm)

    graph = StateGraph(InvestigationState)
    graph.add_node("planner", planner.run)
    graph.add_node("researcher", researcher.run)
    graph.add_node("data_analyst", analyst.run)
    graph.add_node("webhook_inspector", webhooks.run)
    graph.add_node("health", health.run)
    graph.add_node("sufficiency", sufficiency.run)
    graph.add_node("incident_risk", incident.run)
    graph.add_node("verifier", verifier.run)
    graph.add_node("writer", writer.run)
    graph.add_node("critic", critic.run)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "data_analyst")
    graph.add_edge("data_analyst", "webhook_inspector")
    graph.add_edge("webhook_inspector", "health")
    graph.add_edge("health", "sufficiency")
    graph.add_conditional_edges(
        "sufficiency",
        _route_after_sufficiency,
        {"dispatch": "researcher", "writer": "writer", "incident_risk": "incident_risk"},
    )
    graph.add_edge("incident_risk", "verifier")
    graph.add_edge("verifier", "writer")
    graph.add_edge("writer", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {"writer": "writer", "end": END})
    return graph.compile()


def initial_state(
    question: str,
    merchant_id: str | None = None,
    time_window: TimeWindow | None = None,
) -> InvestigationState:
    settings = get_settings()
    return InvestigationState(
        question=question,
        merchant_id=merchant_id,
        time_window=time_window,
        evidence=EvidenceBundle(),
        metrics=[],
        hypotheses=[],
        verified_claims=[],
        trace=[],
        iteration=0,
        max_iterations=settings.max_iterations,
        critic_revisions=0,
        pending_tasks=[],
    )
