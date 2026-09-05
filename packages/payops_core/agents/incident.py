from __future__ import annotations

from payops_core.models.schemas import EvidenceBundle, Hypothesis, MetricResult


class IncidentRiskAgent:
    """Rank hypotheses from collected evidence only. Does not retrieve new evidence."""

    def propose(
        self,
        evidence: EvidenceBundle,
        metrics: list[MetricResult],
        question: str,
    ) -> list[Hypothesis]:
        ids = evidence.ids()
        blob = " ".join(item.text_snippet for item in evidence.items).upper()
        hypotheses: list[Hypothesis] = []
        if "GATEWAY_TIMEOUT" in blob or _breakdown_has(metrics, "GATEWAY_TIMEOUT"):
            hypotheses.append(
                Hypothesis(
                    cause="UPI gateway timeouts at the method processor",
                    supporting_evidence_ids=_ids_for(evidence, ("GATEWAY_TIMEOUT", "timeout")),
                    confidence=0.82,
                    category="processor",
                )
            )
        delayed = any(
            item.source == "webhook" and item.metadata.get("kind") == "delayed"
            for item in evidence.items
        )
        high_risk = any(
            item.source == "ml" and item.metadata.get("risk_class") == "HIGH"
            for item in evidence.items
        )
        if high_risk:
            hypotheses.append(
                Hypothesis(
                    cause="Elevated model-predicted failure risk in the window",
                    supporting_evidence_ids=[
                        item.evidence_id for item in evidence.items if item.source == "ml"
                    ][:5],
                    confidence=0.55,
                    category="model",
                )
            )
        integrity_items = [item for item in evidence.items if item.source == "integrity"]
        if integrity_items:
            passed = all(item.metadata.get("passed") is True for item in integrity_items)
            hypotheses.append(
                Hypothesis(
                    cause=(
                        "Integrity catalog found no consistency violations"
                        if passed
                        else "Integrity catalog found consistency violations"
                    ),
                    supporting_evidence_ids=[item.evidence_id for item in integrity_items][:5],
                    confidence=0.75 if passed else 0.7,
                    category="integrity",
                )
            )
        if delayed:
            hypotheses.append(
                Hypothesis(
                    cause="Webhook delivery delays after successful capture",
                    supporting_evidence_ids=[
                        item.evidence_id for item in evidence.items if item.source == "webhook"
                    ][:5],
                    confidence=0.8,
                    category="webhooks",
                )
            )
        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    cause="Insufficient structured evidence to name a root cause",
                    supporting_evidence_ids=ids[:3],
                    confidence=0.2,
                    category="unknown",
                )
            )
        filled: list[Hypothesis] = []
        for item in hypotheses:
            if item.supporting_evidence_ids or not ids:
                filled.append(item)
            else:
                filled.append(item.model_copy(update={"supporting_evidence_ids": ids[:3]}))
        return filled


def _breakdown_has(metrics: list[MetricResult], code: str) -> bool:
    for metric in metrics:
        if metric.metric == "error_code_breakdown" and isinstance(metric.value, dict):
            if code in metric.value:
                return True
    return False


def _ids_for(evidence: EvidenceBundle, needles: tuple[str, ...]) -> list[str]:
    found = [
        item.evidence_id
        for item in evidence.items
        if any(needle.lower() in item.text_snippet.lower() for needle in needles)
    ]
    return found[:5]
