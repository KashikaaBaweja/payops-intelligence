from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from payops_core.models.schemas import (
    CritiqueResult,
    EvidenceBundle,
    Hypothesis,
    IncidentReport,
    InvestigationPlan,
    MetricResult,
    SufficiencyVerdict,
    Task,
    TimeWindow,
    TraceEvent,
    VerificationResult,
    VerifiedClaim,
)


class InvestigationState(TypedDict, total=False):
    """Shared graph state. Values are structured models, not free-text reasoning."""

    question: str
    merchant_id: str | None
    time_window: TimeWindow | None
    plan: InvestigationPlan | None
    evidence: EvidenceBundle
    metrics: list[MetricResult]
    hypotheses: list[Hypothesis]
    sufficiency: SufficiencyVerdict | None
    verified_claims: list[VerifiedClaim]
    verification: VerificationResult | None
    critique: CritiqueResult | None
    report: IncidentReport | None
    trace: Annotated[list[TraceEvent], operator.add]
    iteration: int
    max_iterations: int
    critic_revisions: int
    pending_tasks: list[Task]
    completed_task_ids: Annotated[list[str], operator.add]
    error: str | None
    timed_out: bool
