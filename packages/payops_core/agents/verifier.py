from __future__ import annotations

from payops_core.models.schemas import EvidenceBundle, Hypothesis, VerifiedClaim


class VerifierAgent:
    """Check hypotheses against evidence IDs already in the bundle."""

    def verify(self, hypotheses: list[Hypothesis], evidence: EvidenceBundle) -> list[VerifiedClaim]:
        known = set(evidence.ids())
        claims: list[VerifiedClaim] = []
        for hypothesis in hypotheses:
            supported_ids = [item for item in hypothesis.supporting_evidence_ids if item in known]
            claims.append(
                VerifiedClaim(
                    claim=hypothesis.cause,
                    evidence_ids=supported_ids,
                    supported=bool(supported_ids),
                    note=None
                    if supported_ids
                    else "hypothesis cited IDs that are not in the bundle",
                )
            )
        return claims
