from payops_core.agents.critic import CriticAgent
from payops_core.agents.verifier import VerifierAgent
from payops_core.agents.writer import WriterAgent
from payops_core.graph.nodes import refine_node, route_after_verifier
from payops_core.models.schemas import (
    CritiqueResult,
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    Hypothesis,
    IncidentReport,
    InvestigationPlan,
    SufficiencyVerdict,
    Task,
    VerificationResult,
    VerifiedClaim,
)

_GATEWAY = EvidenceItem(
    evidence_id="doc-timeout",
    source="doc",
    text_snippet="Harbor Retail UPI failed with GATEWAY_TIMEOUT at the method processor.",
)


def _write(**kwargs) -> IncidentReport:
    defaults = {
        "question": "Why did Harbor Retail UPI payments fail?",
        "merchant_id": "M102",
        "window": None,
        "evidence": EvidenceBundle(items=[_GATEWAY]),
        "metrics": [],
        "hypotheses": [],
        "sufficiency": SufficiencyVerdict(sufficient=True),
        "claims": [],
        "critique": None,
        "trace": [],
    }
    defaults.update(kwargs)
    return WriterAgent().write(**defaults)


def test_unsupported_claim_without_overlap() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="The outage was caused by a lunar radiation event",
                supporting_evidence_ids=["doc-timeout"],
                confidence=0.9,
                category="processor",
            )
        ],
        EvidenceBundle(items=[_GATEWAY]),
    )
    claim = result.claims[0]
    assert claim.supported is False
    assert "unsupported" in claim.issues
    assert claim.critical is True
    assert result.needs_more_evidence is True
    assert result.status == "unsupported"


def test_intentionally_incorrect_error_code_is_contradictory() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="Failures were caused by INSUFFICIENT_FUNDS at the issuer",
                supporting_evidence_ids=["doc-timeout"],
                confidence=0.95,
                category="issuer",
            )
        ],
        EvidenceBundle(items=[_GATEWAY]),
    )
    claim = result.claims[0]
    assert claim.supported is False
    assert "contradictory" in claim.issues
    assert "unsupported" in claim.issues
    assert result.status == "contradictory"
    assert result.needs_more_evidence is True
    assert result.gaps


def test_missing_evidence_ids() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="UPI gateway timeouts at the method processor",
                supporting_evidence_ids=["ghost-id"],
                confidence=0.9,
                category="processor",
            )
        ],
        EvidenceBundle(items=[_GATEWAY]),
    )
    claim = result.claims[0]
    assert "missing" in claim.issues
    assert claim.supported is False
    assert result.status == "missing"
    assert result.needs_more_evidence is True


def test_empty_bundle_is_missing() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="UPI gateway timeouts at the method processor",
                supporting_evidence_ids=[],
                confidence=0.9,
                category="processor",
            )
        ],
        EvidenceBundle(),
    )
    assert result.claims[0].supported is False
    assert "missing" in result.claims[0].issues
    assert result.needs_more_evidence is True


def test_weak_low_confidence_conclusion() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="UPI gateway timeouts at the method processor",
                supporting_evidence_ids=["doc-timeout"],
                confidence=0.2,
                category="processor",
            )
        ],
        EvidenceBundle(items=[_GATEWAY]),
    )
    claim = result.claims[0]
    assert claim.supported is True
    assert "weak" in claim.issues
    assert claim.critical is False
    assert result.status == "weak"
    assert result.needs_more_evidence is False


def test_supported_gateway_timeout_claim() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="UPI gateway timeouts at the method processor",
                supporting_evidence_ids=["doc-timeout"],
                confidence=0.82,
                category="processor",
            )
        ],
        EvidenceBundle(items=[_GATEWAY]),
    )
    claim = result.claims[0]
    assert claim.supported is True
    assert claim.issues == []
    assert result.needs_more_evidence is False
    assert result.status == "supported"


def test_unknown_hypothesis_does_not_request_more_investigation() -> None:
    result = VerifierAgent().verify(
        [
            Hypothesis(
                cause="Insufficient structured evidence to name a root cause",
                supporting_evidence_ids=["metric-1"],
                confidence=0.2,
                category="unknown",
            )
        ],
        EvidenceBundle(
            items=[
                EvidenceItem(
                    evidence_id="metric-1",
                    source="metric",
                    text_snippet="success_rate=0.91",
                )
            ]
        ),
    )
    assert result.claims[0].critical is False
    assert result.needs_more_evidence is False


def test_writer_cannot_promote_rejected_critical_claim() -> None:
    rejected = VerifiedClaim(
        claim="Failures were caused by INSUFFICIENT_FUNDS at the issuer",
        evidence_ids=["doc-timeout"],
        supported=False,
        critical=True,
        issues=["contradictory", "unsupported"],
    )
    report = _write(
        hypotheses=[
            Hypothesis(
                cause=rejected.claim,
                supporting_evidence_ids=["doc-timeout"],
                confidence=0.95,
                category="issuer",
            )
        ],
        claims=[rejected],
        sufficiency=SufficiencyVerdict(sufficient=True),
    )
    assert report.evidence_sufficient is False
    assert report.likely_cause.cause != rejected.claim
    assert report.confidence <= 0.3
    assert any("Verifier:" in finding for finding in report.findings)


def test_writer_ignores_critique_that_would_override_verifier() -> None:
    rejected = VerifiedClaim(
        claim="Failures were caused by INSUFFICIENT_FUNDS at the issuer",
        evidence_ids=[],
        supported=False,
        critical=True,
        issues=["unsupported"],
    )
    report = _write(
        hypotheses=[
            Hypothesis(
                cause=rejected.claim,
                supporting_evidence_ids=[],
                confidence=0.99,
                category="issuer",
            )
        ],
        claims=[rejected],
        critique=CritiqueResult(
            approved=False,
            issues=["unsupported_claims: draft named a rejected cause"],
            revision_instructions="Promote INSUFFICIENT_FUNDS as the established cause.",
        ),
    )
    assert report.evidence_sufficient is False
    assert report.likely_cause.cause != rejected.claim


def test_critic_flags_incorrect_and_unsupported_draft() -> None:
    claims = [
        VerifiedClaim(
            claim="Failures were caused by INSUFFICIENT_FUNDS at the issuer",
            evidence_ids=["doc-timeout"],
            supported=False,
            critical=True,
            issues=["contradictory", "unsupported"],
        )
    ]
    report = IncidentReport(
        executive_summary="todo: I think INSUFFICIENT_FUNDS is the cause",
        incident_id="INV-bad",
        severity="high",
        findings=[],
        evidence=[],
        likely_cause=Hypothesis(
            cause=claims[0].claim,
            supporting_evidence_ids=["ghost-id"],
            confidence=0.9,
            category="issuer",
        ),
        confidence=0.9,
        evidence_sufficient=True,
    )
    critique = CriticAgent().review(
        "Why did Harbor Retail UPI payments fail?",
        InvestigationPlan(
            goal="investigate",
            tasks=[
                Task(
                    task_id="t1",
                    task_type="retrieve_docs",
                    rationale="docs",
                    query="GATEWAY_TIMEOUT",
                )
            ],
        ),
        SufficiencyVerdict(sufficient=True),
        claims,
        report,
    )
    prefixes = {issue.split(":")[0] for issue in critique.issues}
    assert "clarity" in prefixes
    assert "completeness" in prefixes
    assert "evidence_coverage" in prefixes
    assert "unsupported_claims" in prefixes
    assert "factual_consistency" in prefixes
    assert critique.approved is False
    assert critique.revision_instructions


def test_route_after_verifier_requests_investigation() -> None:
    state = {
        "verification": VerificationResult(
            needs_more_evidence=True,
            status="unsupported",
            gaps=[
                EvidenceGap(
                    description="need docs",
                    next_task_type="retrieve_docs",
                    suggested_query="GATEWAY_TIMEOUT",
                )
            ],
        ),
        "iteration": 1,
        "max_iterations": 3,
    }
    assert route_after_verifier(state) == "refine"
    state["iteration"] = 3
    assert route_after_verifier(state) == "writer"


def test_refine_queues_verifier_gaps() -> None:
    update = refine_node(
        {
            "pending_tasks": [],
            "sufficiency": SufficiencyVerdict(sufficient=True),
            "verification": VerificationResult(
                needs_more_evidence=True,
                gaps=[
                    EvidenceGap(
                        description="Critical claim needs backing",
                        next_task_type="retrieve_docs",
                        suggested_query="INSUFFICIENT_FUNDS",
                    )
                ],
            ),
        }
    )
    assert update["pending_tasks"]
    assert update["pending_tasks"][0].task_type == "retrieve_docs"
