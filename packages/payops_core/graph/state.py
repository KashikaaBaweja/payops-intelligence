from typing import TypedDict

from payops_core.models import (
    CritiqueResult,
    EvidenceBundle,
    Hypothesis,
    IncidentReport,
    InvestigationPlan,
    MetricResult,
    SufficiencyVerdict,
    TimeWindow,
    TraceEvent,
    VerifiedClaim,
)


class InvestigationState(TypedDict, total=False):
    question: str
    merchant_id: str | None
    time_window: TimeWindow | None
    plan: InvestigationPlan | None
    evidence: EvidenceBundle
    metrics: list[MetricResult]
    hypotheses: list[Hypothesis]
    sufficiency: SufficiencyVerdict | None
    verified_claims: list[VerifiedClaim]
    critique: CritiqueResult | None
    report: IncidentReport | None
    trace: list[TraceEvent]
    iteration: int
    max_iterations: int
    critic_revisions: int
    pending_tasks: list[dict]
