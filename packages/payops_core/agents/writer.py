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
    """Write a structured report from closed evidence. No new retrieval."""

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
        cause = (hypotheses[0] if hypotheses else Hypothesis(
            cause="Insufficient structured evidence to name a root cause",
            supporting_evidence_ids=[],
            confidence=0.2,
            category="unknown",
        )).model_copy(
            update={
                "supporting_evidence_ids": [
                    item
                    for item in (hypotheses[0].supporting_evidence_ids if hypotheses else [])
                    if item in known
                ]
            }
        )
        refs = [
            EvidenceRef(
                evidence_id=item.evidence_id,
                source=item.source,
                label=item.section or item.source,
            )
            for item in evidence.items
        ]
        findings = [item.text_snippet[:180] for item in evidence.items[:8]]
        if error:
            findings.insert(0, f"Investigation failed: {error}")
        if timed_out:
            findings.insert(0, "Investigation timed out")
        if not sufficient:
            findings.append("Evidence was insufficient for a confident root cause.")
        summary = _summary(question, sufficient, cause, timed_out, error)
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
            confidence=cause.confidence if sufficient else min(cause.confidence, 0.3),
            recommended_actions=_actions(sufficient, cause.category),
            sources=refs,
            agent_execution_summary=trace,
            evidence_sufficient=sufficient,
        )


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
