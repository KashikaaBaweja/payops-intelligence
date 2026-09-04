from __future__ import annotations

from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceGap,
    InvestigationPlan,
    SufficiencyVerdict,
    Task,
)

_SOURCE_FOR_TASK = {
    "retrieve_docs": "doc",
    "query_metrics": "metric",
    "inspect_webhooks": "webhook",
    "compare_merchants": "metric",
    "merchant_health": "health",
}


class SufficiencyAgent:
    """Decide whether planned evidence categories are present. No LLM."""

    def evaluate(
        self,
        plan: InvestigationPlan | None,
        evidence: EvidenceBundle,
    ) -> SufficiencyVerdict:
        if plan is None or not plan.tasks:
            return SufficiencyVerdict(
                sufficient=False,
                missing=[
                    EvidenceGap(
                        description="No investigation plan",
                        next_task_type="retrieve_docs",
                    )
                ],
                next_action="investigate",
                reason="planner produced no tasks",
            )
        present = {item.source for item in evidence.items}
        missing: list[EvidenceGap] = []
        for task in plan.tasks:
            needed = _SOURCE_FOR_TASK.get(task.task_type, "doc")
            if needed not in present:
                missing.append(
                    EvidenceGap(
                        description=f"Missing {needed} evidence for {task.task_type}",
                        next_task_type=task.task_type,
                        suggested_query=task.query,
                    )
                )
        if missing:
            return SufficiencyVerdict(
                sufficient=False,
                missing=missing,
                next_action="investigate",
                reason="planned evidence categories are incomplete",
            )
        return SufficiencyVerdict(
            sufficient=True,
            missing=[],
            next_action="verify",
            reason="all planned evidence categories are present",
        )


def task_from_gap(gap: EvidenceGap, index: int) -> Task:
    return Task(
        task_id=f"gap-{index}-{gap.next_task_type}",
        task_type=gap.next_task_type,  # type: ignore[arg-type]
        rationale=gap.description,
        query=gap.suggested_query,
        evidence_category=gap.next_task_type,
    )
