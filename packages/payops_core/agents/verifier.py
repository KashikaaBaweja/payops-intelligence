from __future__ import annotations

import re
from typing import Literal

from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceGap,
    Hypothesis,
    VerificationResult,
    VerifiedClaim,
)

Issue = Literal["unsupported", "contradictory", "missing", "weak"]

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "for",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}
_GENERIC = {
    "after",
    "also",
    "cause",
    "caused",
    "code",
    "codes",
    "during",
    "event",
    "events",
    "fail",
    "failed",
    "failure",
    "failures",
    "incident",
    "issue",
    "merchant",
    "method",
    "outage",
    "payment",
    "payments",
    "platform",
    "problem",
    "processor",
    "rate",
    "success",
    "successful",
}
_ERROR_CODES = (
    "GATEWAY_TIMEOUT",
    "INSUFFICIENT_FUNDS",
    "DO_NOT_HONOR",
    "AUTHENTICATION_FAILED",
    "WEBHOOK_TIMEOUT",
)
_OPPOSITES: dict[str, set[str]] = {
    "GATEWAY_TIMEOUT": {"INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "AUTHENTICATION_FAILED"},
    "INSUFFICIENT_FUNDS": {"GATEWAY_TIMEOUT"},
    "DO_NOT_HONOR": {"GATEWAY_TIMEOUT"},
    "AUTHENTICATION_FAILED": {"GATEWAY_TIMEOUT"},
    "WEBHOOK_TIMEOUT": {"GATEWAY_TIMEOUT"},
}


class VerifierAgent:
    """Check claims against collected evidence. Does not invent new facts."""

    def verify(
        self,
        hypotheses: list[Hypothesis],
        evidence: EvidenceBundle,
    ) -> VerificationResult:
        claims = [
            self._check(hypothesis, evidence, index == 0)
            for index, hypothesis in enumerate(hypotheses)
        ]
        gaps = [_gap_for(claim) for claim in claims if claim.critical and not claim.supported]
        return VerificationResult(
            claims=claims,
            needs_more_evidence=bool(gaps),
            gaps=gaps,
            status=_overall_status(claims),
        )

    def _check(
        self,
        hypothesis: Hypothesis,
        evidence: EvidenceBundle,
        leading: bool,
    ) -> VerifiedClaim:
        known = {item.evidence_id: item for item in evidence.items}
        cited = [item_id for item_id in hypothesis.supporting_evidence_ids if item_id in known]
        missing_ids = [
            item_id for item_id in hypothesis.supporting_evidence_ids if item_id not in known
        ]
        snippets = [known[item_id].text_snippet for item_id in cited] or [
            item.text_snippet for item in evidence.items
        ]
        blob = " ".join(snippets)
        overlap = _stems(_tokens(hypothesis.cause)) & _stems(_tokens(blob))
        distinctive = {token for token in overlap if token not in _GENERIC}
        claim_codes = _codes(hypothesis.cause)
        evidence_codes = _codes(blob)
        shared_codes = claim_codes & evidence_codes
        issues: list[Issue] = []
        if not evidence.items or (hypothesis.supporting_evidence_ids and not cited):
            issues.append("missing")
        elif missing_ids and not cited:
            issues.append("missing")
        if _contradictory(claim_codes, evidence_codes):
            issues.append("contradictory")
        grounded = bool(distinctive or shared_codes) and "contradictory" not in issues
        supported = grounded and "missing" not in issues
        if not supported and "unsupported" not in issues:
            issues.append("unsupported")
        weak = supported and (
            hypothesis.confidence < 0.4 or (len(distinctive) < 2 and not shared_codes)
        )
        if weak:
            issues.append("weak")
        critical = leading and hypothesis.confidence >= 0.6 and hypothesis.category != "unknown"
        return VerifiedClaim(
            claim=hypothesis.cause,
            evidence_ids=cited,
            supported=supported,
            critical=critical,
            issues=issues,
            note=", ".join(issues) if issues else None,
        )


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _TOKEN.findall(text.lower()):
        if token in _STOPWORDS or len(token) <= 2:
            continue
        tokens.add(token)
        if "_" in token:
            tokens.update(
                part for part in token.split("_") if part not in _STOPWORDS and len(part) > 2
            )
    return tokens


def _stems(tokens: set[str]) -> set[str]:
    stems = set(tokens)
    for token in tokens:
        for suffix in ("ing", "ion", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) > 2:
                stems.add(token[: -len(suffix)])
    return stems


def _codes(text: str) -> set[str]:
    compact = text.upper().replace("-", "_").replace(" ", "_")
    return {code for code in _ERROR_CODES if code in compact}


def _contradictory(claim_codes: set[str], evidence_codes: set[str]) -> bool:
    if not claim_codes or not evidence_codes:
        return False
    for code in claim_codes:
        opposites = _OPPOSITES.get(code, set())
        if evidence_codes & opposites and code not in evidence_codes:
            return True
    return False


def _gap_for(claim: VerifiedClaim) -> EvidenceGap:
    lowered = claim.claim.lower()
    if "webhook" in lowered or "ack" in lowered:
        task_type = "inspect_webhooks"
    elif "rate" in lowered or "success" in lowered or "failure" in lowered:
        task_type = "query_metrics"
    else:
        task_type = "retrieve_docs"
    return EvidenceGap(
        description=f"Critical claim needs backing: {claim.claim}",
        next_task_type=task_type,
        suggested_query=claim.claim,
    )


def _overall_status(claims: list[VerifiedClaim]) -> str:
    if any("contradictory" in claim.issues for claim in claims):
        return "contradictory"
    if any("missing" in claim.issues for claim in claims if claim.critical):
        return "missing"
    if any(not claim.supported for claim in claims if claim.critical):
        return "unsupported"
    if any("weak" in claim.issues for claim in claims):
        return "weak"
    if claims and all(claim.supported for claim in claims):
        return "supported"
    return "unsupported"
