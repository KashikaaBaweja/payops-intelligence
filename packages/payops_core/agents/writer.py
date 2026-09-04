from __future__ import annotations

from hashlib import sha1

from payops_core.models.schemas import (
    CritiqueResult,
    EvidenceBundle,
    EvidenceRef,
    Hypothesis,
    IncidentReport,
    MetricResult,
    SufficiencyVerdict,
    TimeWindow,
    TraceEvent,
    VerifiedClaim,
)


class WriterAgent:
    """Write a structured report from closed evidence. Cannot override verifier findings."""

    def write(
        self,
        question: str,
        merchant_id: str | None,
        window: TimeWindow | None,
        evidence: EvidenceBundle,
        metrics: list[MetricResult],
        hypotheses: list[Hypothesis],
        sufficiency: SufficiencyVerdict | None,
        claims: list[VerifiedClaim],
        critique: CritiqueResult | None,
        trace: list[TraceEvent],
        error: str | None = None,
        timed_out: bool = False,
    ) -> IncidentReport:
        known = set(evidence.ids())
        sufficient = bool(sufficiency and sufficiency.sufficient and not timed_out and not error)
        if any(claim.critical and not claim.supported for claim in claims):
            sufficient = False
        if any("contradictory" in claim.issues for claim in claims if claim.critical):
            sufficient = False
        cause = _cause(hypotheses, claims, known, sufficient)
        refs = [
            EvidenceRef(
                evidence_id=item.evidence_id,
                source=item.source,
                label=item.section or item.source,
            )
            for item in evidence.items
        ]
        findings = [item.text_snippet[:180] for item in evidence.items[:8]]
        findings.extend(_verifier_notes(claims))
        if critique and critique.revision_instructions:
            findings.append(critique.revision_instructions)
        if error:
            findings.insert(0, f"Investigation failed: {error}")
        if timed_out:
            findings.insert(0, "Investigation timed out")
        if not sufficient:
            findings.append("Evidence was insufficient for a confident root cause.")
        summary = _summary(question, sufficient, cause, timed_out, error)
        confidence = cause.confidence if sufficient else min(cause.confidence, 0.3)
        if any("weak" in claim.issues for claim in claims):
            confidence = min(confidence, 0.4)
        return IncidentReport(
            executive_summary=summary,
            merchant_id=merchant_id,
            incident_id=_incident_id(question, merchant_id),
            time_window=window,
            severity=_severity(metrics, evidence, sufficient),
            observed_metrics=metrics,
            findings=findings,
            evidence=refs,
            likely_cause=cause,
            alternative_hypotheses=hypotheses[1:3],
            confidence=confidence,
            recommended_actions=_actions(sufficient, cause.category),
            sources=refs,
            agent_execution_summary=trace,
            evidence_sufficient=sufficient,
        )


def _cause(
    hypotheses: list[Hypothesis],
    claims: list[VerifiedClaim],
    known: set[str],
    sufficient: bool,
) -> Hypothesis:
    fallback = Hypothesis(
        cause="Insufficient structured evidence to name a root cause",
        supporting_evidence_ids=[],
        confidence=0.2,
        category="unknown",
    )
    if not claims and hypotheses:
        hyp = hypotheses[0]
        return hyp.model_copy(
            update={
                "supporting_evidence_ids": [
                    item_id for item_id in hyp.supporting_evidence_ids if item_id in known
                ],
                "confidence": hyp.confidence if sufficient else min(hyp.confidence, 0.3),
            }
        )
    supported = [claim for claim in claims if claim.supported]
    if not supported:
        return fallback
    chosen = supported[0]
    match = next((item for item in hypotheses if item.cause == chosen.claim), None)
    if match is None:
        return Hypothesis(
            cause=chosen.claim,
            supporting_evidence_ids=chosen.evidence_ids,
            confidence=0.5 if sufficient else 0.3,
            category="verified",
        )
    return match.model_copy(
        update={
            "supporting_evidence_ids": [
                item_id for item_id in chosen.evidence_ids if item_id in known
            ]
        }
    )


def _verifier_notes(claims: list[VerifiedClaim]) -> list[str]:
    notes: list[str] = []
    for claim in claims:
        if claim.issues:
            notes.append(f"Verifier: {claim.claim} [{', '.join(claim.issues)}]")
    return notes


def _summary(
    question: str,
    sufficient: bool,
    cause: Hypothesis,
    timed_out: bool,
    error: str | None,
) -> str:
    if timed_out:
        return f"Timed out while investigating: {question}"
    if error:
        return f"Failed while investigating: {question}"
    if not sufficient:
        return f"Incomplete investigation for: {question}"
    return f"Investigation of '{question}' points to {cause.cause}."


def _incident_id(question: str, merchant_id: str | None) -> str:
    digest = sha1(question.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    prefix = merchant_id or "INV"
    return f"{prefix}-{digest}"


def _severity(metrics: list[MetricResult], evidence: EvidenceBundle, sufficient: bool) -> str:
    if not sufficient:
        return "low"
    for metric in metrics:
        if (
            metric.metric == "failure_rate"
            and isinstance(metric.value, float)
            and metric.value >= 0.5
        ):
            return "high"
    if any(item.metadata.get("kind") == "delayed" for item in evidence.items):
        return "medium"
    return "low"


def _actions(sufficient: bool, category: str) -> list[str]:
    if not sufficient:
        return ["Collect additional evidence before naming a root cause."]
    if category == "processor":
        return ["Fail over the affected method", "Page the processor"]
    if category == "webhooks":
        return ["Inspect delayed ACK consumers", "Do not treat delayed webhooks as declines"]
    return ["Review the cited evidence with ops"]
