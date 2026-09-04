from __future__ import annotations

from payops_core.models.schemas import (
    CritiqueResult,
    IncidentReport,
    InvestigationPlan,
    SufficiencyVerdict,
    VerifiedClaim,
)


class CriticAgent:
    """Evaluate a draft report. Does not retrieve new evidence or override the verifier."""

    def review(
        self,
        question: str,
        plan: InvestigationPlan | None,
        sufficiency: SufficiencyVerdict | None,
        claims: list[VerifiedClaim],
        report: IncidentReport | None = None,
    ) -> CritiqueResult:
        issues: list[str] = []
        if not question.strip():
            issues.append("clarity: empty question")
        if plan is None:
            issues.append("completeness: missing investigation plan")
        if report is None:
            issues.append("completeness: missing draft report")
            return CritiqueResult(
                approved=False,
                issues=issues,
                revision_instructions="Produce a draft from verified evidence only.",
            )
        issues.extend(_clarity(report))
        issues.extend(_completeness(question, report))
        issues.extend(_coverage(report))
        issues.extend(_unsupported(claims, report))
        issues.extend(_consistency(claims, report))
        if sufficiency is not None and not sufficiency.sufficient:
            issues.append("completeness: evidence marked insufficient")
        approved = not any(
            item.startswith(("unsupported_claims", "factual_consistency", "evidence_coverage"))
            for item in issues
        ) and bool(report.executive_summary)
        instructions = None
        if not approved:
            instructions = "Revise using verifier findings only. Do not promote unsupported claims."
        return CritiqueResult(
            approved=approved,
            issues=issues,
            revision_instructions=instructions,
        )


def _clarity(report: IncidentReport) -> list[str]:
    issues: list[str] = []
    summary = report.executive_summary.strip()
    if len(summary) < 20:
        issues.append("clarity: executive summary is too short")
    lowered = summary.lower()
    if "todo" in lowered or "i think" in lowered:
        issues.append("clarity: draft contains speculative language")
    return issues


def _completeness(question: str, report: IncidentReport) -> list[str]:
    issues: list[str] = []
    if not report.findings:
        issues.append("completeness: report has no findings")
    if not report.evidence:
        issues.append("completeness: report cites no evidence")
    q_tokens = {token for token in question.lower().split() if len(token) > 3}
    blob = f"{report.executive_summary} {' '.join(report.findings)}".lower()
    if q_tokens and not (q_tokens & set(blob.split())):
        issues.append("completeness: draft does not address the question")
    return issues


def _coverage(report: IncidentReport) -> list[str]:
    cited = {item.evidence_id for item in report.evidence}
    missing = [
        item_id for item_id in report.likely_cause.supporting_evidence_ids if item_id not in cited
    ]
    if missing:
        return ["evidence_coverage: likely cause cites IDs absent from the report"]
    return []


_FALLBACK_CAUSE = "Insufficient structured evidence to name a root cause"


def _unsupported(claims: list[VerifiedClaim], report: IncidentReport) -> list[str]:
    rejected = {claim.claim for claim in claims if not claim.supported}
    if (
        report.likely_cause.cause in rejected
        and report.evidence_sufficient
        and report.likely_cause.cause != _FALLBACK_CAUSE
    ):
        return ["unsupported_claims: writer treated a rejected claim as established"]
    if (
        any(claim.critical and not claim.supported for claim in claims)
        and report.evidence_sufficient
    ):
        return ["unsupported_claims: evidence_sufficient ignores verifier"]
    return []


def _consistency(claims: list[VerifiedClaim], report: IncidentReport) -> list[str]:
    if any("contradictory" in claim.issues for claim in claims if claim.critical):
        if report.confidence > 0.4:
            return ["factual_consistency: high confidence despite contradictory evidence"]
    return []
