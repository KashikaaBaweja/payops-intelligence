from __future__ import annotations

from payops_core.models.schemas import (
    CritiqueResult,
    InvestigationPlan,
    SufficiencyVerdict,
    VerifiedClaim,
)


class CriticAgent:
    """Review completeness before writing. Does not retrieve new evidence."""

    def review(
        self,
        question: str,
        plan: InvestigationPlan | None,
        sufficiency: SufficiencyVerdict | None,
        claims: list[VerifiedClaim],
    ) -> CritiqueResult:
        issues: list[str] = []
        if not question.strip():
            issues.append("empty question")
        if plan is None:
            issues.append("missing investigation plan")
        if sufficiency is None:
            issues.append("missing sufficiency verdict")
        unsupported = [claim.claim for claim in claims if not claim.supported]
        if unsupported:
            issues.append("unsupported claims present")
        if sufficiency is not None and not sufficiency.sufficient:
            issues.append("evidence marked insufficient")
        approved = not unsupported and bool(sufficiency and sufficiency.sufficient)
        instructions = None
        if not approved:
            instructions = "Write an incomplete report; do not invent evidence."
        return CritiqueResult(
            approved=approved,
            issues=issues,
            revision_instructions=instructions,
        )
