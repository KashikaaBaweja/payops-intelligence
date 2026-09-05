from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimeWindow(BaseModel):
    start: datetime
    end: datetime

    def token(self) -> str:
        return f"{self.start.strftime('%Y%m%d')}-{self.end.strftime('%Y%m%d')}"


def evidence_scope(merchant_id: str | None, window: TimeWindow | None) -> str:
    """Stable, window-scoped suffix so catalog reads do not collide."""
    merchant = merchant_id or "all"
    return f"{merchant}-{window.token()}" if window is not None else merchant


class Task(BaseModel):
    task_id: str
    task_type: Literal[
        "retrieve_docs",
        "query_metrics",
        "inspect_webhooks",
        "compare_merchants",
        "merchant_health",
        "score_risk",
        "score_regression",
        "validate_integrity",
    ]
    rationale: str
    query: str | None = None
    merchant_id: str | None = None
    method_id: str | None = None
    evidence_category: str = "general"


class InvestigationPlan(BaseModel):
    goal: str
    merchant_id: str | None = None
    time_window: TimeWindow | None = None
    tasks: list[Task]


class RetrievalHit(BaseModel):
    document_id: str
    chunk_id: str
    source: str
    section: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_evidence(self) -> "EvidenceItem":
        return EvidenceItem(
            evidence_id=f"doc-{self.chunk_id}",
            source="doc",
            doc_id=self.document_id,
            section=self.section,
            chunk_id=self.chunk_id,
            score=self.score,
            text_snippet=self.text[:500],
            metadata=self.metadata,
        )


class EvidenceItem(BaseModel):
    evidence_id: str
    source: Literal["doc", "metric", "webhook", "health", "ml", "integrity"]
    doc_id: str | None = None
    section: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    text_snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)

    def ids(self) -> list[str]:
        return [item.evidence_id for item in self.items]


class SearchQuery(BaseModel):
    query: str
    doc_type: str | None = None
    rationale: str = ""


class QueryAnalysis(BaseModel):
    """Structured query facets. Not private model reasoning."""

    question: str
    facets: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    tokens: list[str] = Field(default_factory=list)


class RetrievalRound(BaseModel):
    search_index: int
    query: str
    rewritten_from: str | None = None
    rewrite_reason: str | None = None
    retrieved: int
    kept: int
    rejected: int
    sufficient: bool
    decision: Literal["sufficient", "rewrite", "exhausted", "no_results"]
    latency_ms: float
    evidence_ids: list[str] = Field(default_factory=list)
    missing_facets: list[str] = Field(default_factory=list)


class SourceCitation(BaseModel):
    evidence_id: str
    document_id: str
    section: str
    score: float


class AgenticRagResult(BaseModel):
    """Bounded retrieve → evaluate → rewrite loop. Not a chatbot answer."""

    question: str
    analysis: QueryAnalysis
    rounds: list[RetrievalRound] = Field(default_factory=list)
    iterations: int = 0
    max_iterations: int = 3
    latency_ms: float = 0
    sufficient: bool = False
    conflicting: bool = False
    conflict_note: str | None = None
    queries: list[SearchQuery] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    citations: list[SourceCitation] = Field(default_factory=list)
    grounded_excerpt: str = ""
    rejected_count: int = 0
    sources_verified: bool = False


class RetrievalSummary(BaseModel):
    """Safe retrieval metadata for the investigation report."""

    iterations: int = 0
    max_iterations: int = 0
    latency_ms: float = 0
    sufficient: bool = False
    conflicting: bool = False
    conflict_note: str | None = None
    grounded_excerpt: str = ""
    citations: list[SourceCitation] = Field(default_factory=list)
    rounds: list[RetrievalRound] = Field(default_factory=list)


class ResearcherResult(BaseModel):
    """Retrieved evidence only. This is not a final investigation answer."""

    question: str
    queries: list[SearchQuery] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    rejected_count: int = 0
    rag: AgenticRagResult | None = None


AnalyticsOperation = Literal[
    "get_success_rate",
    "get_failure_rate",
    "breakdown_by_method",
    "breakdown_by_error_code",
    "compare_time_windows",
    "compare_merchants",
    "get_refund_rate",
    "get_dispute_rate",
    "get_webhook_failure_rate",
]


class AnalyticsRequest(BaseModel):
    """Validated catalog call. Extra fields (including raw SQL) are rejected."""

    model_config = ConfigDict(extra="forbid")

    operation: AnalyticsOperation
    window: TimeWindow
    merchant_id: str | None = None
    method_id: str | None = None
    compare_merchant_id: str | None = None
    previous_window: TimeWindow | None = None
    compare_metric: Literal["success_rate", "failure_rate"] = "success_rate"


class MetricResult(BaseModel):
    metric: str
    value: float | dict[str, Any]
    window: TimeWindow | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    tool: str = "sql_gateway"
    source: str = "payments"
    operation: str
    merchant_id: str | None = None
    unit: str = "ratio"
    notes: str | None = None
    sample_size: int | None = None

    def to_evidence(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"metric-{self.operation}-{evidence_scope(self.merchant_id, self.window)}",
            source="metric",
            score=None,
            text_snippet=f"{self.metric}={self.value}",
            metadata={
                "metric": self.metric,
                "operation": self.operation,
                "tool": self.tool,
                "source": self.source,
                "filters": self.filters,
                "sample_size": self.sample_size,
            },
        )


class AnalystResult(BaseModel):
    """Metric evidence only. This is not a final investigation report."""

    question: str
    operations: list[str] = Field(default_factory=list)
    metrics: list[MetricResult] = Field(default_factory=list)


WebhookOperation = Literal[
    "get_events_for_payment",
    "find_missing_events",
    "find_delayed_events",
    "get_delivery_failures",
    "find_retries",
    "find_duplicate_events",
    "correlate_events_and_payments",
]


class WebhookRequest(BaseModel):
    """Validated webhook catalog call. Extra fields (including raw SQL) are rejected."""

    model_config = ConfigDict(extra="forbid")

    operation: WebhookOperation
    window: TimeWindow | None = None
    merchant_id: str | None = None
    payment_id: str | None = None
    delay_threshold_ms: int = 30_000


class WebhookFinding(BaseModel):
    kind: Literal["event", "missing", "delayed", "failed", "retry", "duplicate", "mismatch"]
    payment_id: str
    order_id: str | None = None
    merchant_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    event_type: str | None = None
    delivery_status: str | None = None
    delay_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    def to_evidence(self) -> EvidenceItem:
        suffix = self.event_ids[0] if self.event_ids else "none"
        return EvidenceItem(
            evidence_id=f"webhook-{self.kind}-{self.payment_id}-{suffix}",
            source="webhook",
            text_snippet=f"{self.kind} payment={self.payment_id} events={self.event_ids}",
            metadata={
                "kind": self.kind,
                "payment_id": self.payment_id,
                "order_id": self.order_id,
                "merchant_id": self.merchant_id,
                "event_ids": self.event_ids,
                "event_type": self.event_type,
                "delivery_status": self.delivery_status,
                "delay_ms": self.delay_ms,
                **self.details,
            },
        )


class WebhookToolResult(BaseModel):
    operation: str
    findings: list[WebhookFinding] = Field(default_factory=list)
    count: int = 0
    window: TimeWindow | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    tool: str = "webhook_gateway"
    source: str = "webhook_events"

    def to_evidence_items(self) -> list[EvidenceItem]:
        return [item.to_evidence() for item in self.findings]


class WebhookInspectorResult(BaseModel):
    """Webhook findings only. This is not a final investigation report."""

    question: str
    operations: list[str] = Field(default_factory=list)
    results: list[WebhookToolResult] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)


class Hypothesis(BaseModel):
    cause: str
    supporting_evidence_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    category: str = "unknown"


class EvidenceGap(BaseModel):
    description: str
    next_task_type: str
    suggested_query: str | None = None


class SufficiencyVerdict(BaseModel):
    sufficient: bool
    missing: list[EvidenceGap] = Field(default_factory=list)
    next_action: str = "continue"
    reason: str = ""


class VerifiedClaim(BaseModel):
    claim: str
    evidence_ids: list[str]
    supported: bool
    critical: bool = False
    issues: list[Literal["unsupported", "contradictory", "missing", "weak"]] = Field(
        default_factory=list
    )
    note: str | None = None


class VerificationResult(BaseModel):
    claims: list[VerifiedClaim] = Field(default_factory=list)
    needs_more_evidence: bool = False
    gaps: list[EvidenceGap] = Field(default_factory=list)
    status: Literal["supported", "unsupported", "contradictory", "weak", "missing"] = "unsupported"


class CritiqueResult(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    revision_instructions: str | None = None


class EvidenceRef(BaseModel):
    evidence_id: str
    source: str
    label: str


class TraceEvent(BaseModel):
    """Safe execution trace. No private chain-of-thought or model scratchpads."""

    node: str
    action: str
    tool: str | None = None
    search_query: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    decision: str | None = None
    verification_status: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentReport(BaseModel):
    executive_summary: str
    merchant_id: str | None = None
    incident_id: str
    time_window: TimeWindow | None = None
    severity: Literal["low", "medium", "high", "critical"]
    observed_metrics: list[MetricResult] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    likely_cause: Hypothesis
    alternative_hypotheses: list[Hypothesis] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    recommended_actions: list[str] = Field(default_factory=list)
    sources: list[EvidenceRef] = Field(default_factory=list)
    agent_execution_summary: list[TraceEvent] = Field(default_factory=list)
    evidence_sufficient: bool
    retrieval: RetrievalSummary | None = None


class HealthFactor(BaseModel):
    name: str
    weight: float
    value: float
    score: float
    band: Literal["healthy", "degraded", "critical"]
    explanation: str


class HealthPenalty(BaseModel):
    factor: str
    points: float
    reason: str


class MerchantHealthScore(BaseModel):
    """Deterministic merchant health. Every point is attributable to a named factor."""

    merchant_id: str
    window: TimeWindow | None = None
    score: float = Field(ge=0, le=100)
    band: Literal["healthy", "degraded", "critical"]
    factors: list[HealthFactor]
    factor_values: dict[str, float]
    penalties: list[HealthPenalty] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    def to_evidence(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"health-{evidence_scope(self.merchant_id, self.window)}",
            source="health",
            text_snippet=(
                f"health_score={self.score} band={self.band} "
                f"success_rate={self.factor_values.get('success_rate')}"
            ),
            metadata={
                "score": self.score,
                "band": self.band,
                "factor_values": self.factor_values,
                "penalties": [item.model_dump() for item in self.penalties],
            },
        )


class RiskContribution(BaseModel):
    feature: str
    coefficient: float
    value: float
    contribution: float
    explanation: str


class ConfusionMatrix(BaseModel):
    true_negative: int
    false_positive: int
    false_negative: int
    true_positive: int


class ModelCard(BaseModel):
    task: Literal["classification", "regression"]
    algorithm: str
    target: str
    model_version: str
    dataset_version: str
    feature_names: list[str]
    train_rows: int
    test_rows: int


class ClassificationQuality(BaseModel):
    """Holdout classification metrics for the failed class, plus overall accuracy."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None = None
    positive_support: int
    test_size: int
    confusion_matrix: ConfusionMatrix


class RegressionQuality(BaseModel):
    mae: float
    rmse: float
    r2: float
    test_size: int


class ModelQuality(ClassificationQuality):
    """Legacy alias used by older risk payloads. Classification only."""


class MerchantRiskScore(BaseModel):
    """Window-level classification signal. Not a fraud decision."""

    merchant_id: str
    window: TimeWindow | None = None
    sample_size: int
    fail_count: int
    prediction: str
    risk_probability: float = Field(ge=0, le=1)
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    risk_class: Literal["LOW", "MEDIUM", "HIGH"]
    expected_loss_cents: int = 0
    currency: str = "INR"
    features: dict[str, float] = Field(default_factory=dict)
    contributions: list[RiskContribution] = Field(default_factory=list)
    quality: ClassificationQuality
    card: ModelCard | None = None
    next_action: Literal["monitor", "investigate"]
    notes: str

    def to_evidence(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"ml-{evidence_scope(self.merchant_id, self.window)}",
            source="ml",
            text_snippet=(
                f"Predicted failure risk={self.risk_class} p={self.risk_probability:.2f}. "
                "Classification only; not a fraud decision."
            ),
            metadata={
                "task": "classification",
                "prediction": self.prediction,
                "risk_class": self.risk_class,
                "risk_probability": self.risk_probability,
                "class_probabilities": self.class_probabilities,
                "sample_size": self.sample_size,
                "next_action": self.next_action,
                "accuracy": self.quality.accuracy,
                "precision": self.quality.precision,
                "recall": self.quality.recall,
                "f1": self.quality.f1,
                "roc_auc": self.quality.roc_auc,
                "model_version": self.card.model_version if self.card else None,
                "dataset_version": self.card.dataset_version if self.card else None,
            },
        )


class RegressionScore(BaseModel):
    """Capture-latency regression. Separate from the failure classifier."""

    merchant_id: str
    window: TimeWindow | None = None
    sample_size: int
    target: str = "capture_latency_seconds"
    prediction: float
    unit: str = "seconds"
    features: dict[str, float] = Field(default_factory=dict)
    contributions: list[RiskContribution] = Field(default_factory=list)
    quality: RegressionQuality
    card: ModelCard
    notes: str

    def to_evidence(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"ml-reg-{evidence_scope(self.merchant_id, self.window)}",
            source="ml",
            text_snippet=(
                f"Predicted {self.target}={self.prediction:.2f} {self.unit}. "
                f"MAE={self.quality.mae} RMSE={self.quality.rmse} R2={self.quality.r2}."
            ),
            metadata={
                "task": "regression",
                "prediction": self.prediction,
                "target": self.target,
                "unit": self.unit,
                "sample_size": self.sample_size,
                "mae": self.quality.mae,
                "rmse": self.quality.rmse,
                "r2": self.quality.r2,
                "model_version": self.card.model_version,
                "dataset_version": self.card.dataset_version,
            },
        )


class IntegrityCheck(BaseModel):
    check_id: str
    name: str
    passed: bool
    observed: int
    invariant: str
    explanation: str


class IntegrityReport(BaseModel):
    """Read-time consistency checks. Not a commit/rollback simulator."""

    merchant_id: str | None = None
    window: TimeWindow | None = None
    passed: bool
    sample_size: int
    checks: list[IntegrityCheck]
    schema_invariants: list[str] = Field(default_factory=list)
    notes: str

    def to_evidence(self) -> EvidenceItem:
        failed = [item.check_id for item in self.checks if not item.passed]
        return EvidenceItem(
            evidence_id=f"integrity-{evidence_scope(self.merchant_id, self.window)}",
            source="integrity",
            text_snippet=(
                "integrity pass: no consistency violations in payment and order checks"
                if self.passed
                else (
                    "integrity fail: consistency violations in payment and order checks "
                    f"failed={failed}"
                )
            ),
            metadata={
                "passed": self.passed,
                "failed_checks": failed,
                "sample_size": self.sample_size,
                "checks": [item.model_dump() for item in self.checks],
                "schema_invariants": self.schema_invariants,
            },
        )


class LedgerAccountView(BaseModel):
    account_id: str
    merchant_id: str | None = None
    kind: str
    currency: str
    balance_cents: int
    version: int
    status: str


class TransferOperation(BaseModel):
    name: str
    state: str
    account_id: str | None = None
    delta_cents: int | None = None


class TransferAuditEvent(BaseModel):
    audit_id: str
    event: str
    detail: str
    created_at: datetime


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_account_id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$",
    )
    to_account_id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$",
    )
    amount_cents: int = Field(gt=0, le=10_000_000)
    fail_at: Literal["after_debit", "after_credit", "after_ledger", "before_commit"] | None = None


class TransferResult(BaseModel):
    """Outcome of a real database debit/credit/ledger transaction."""

    transfer_id: str
    status: Literal["committed", "rolled_back"]
    current_state: str
    from_account_id: str
    to_account_id: str
    amount_cents: int
    isolation_level: str
    isolation_reason: str
    fail_at: str | None = None
    failure_point: str | None = None
    before_balance: dict[str, int]
    after_balance: dict[str, int]
    operations: list[TransferOperation]
    commit_or_rollback: Literal["COMMIT", "ROLLBACK"]
    audit_events: list[TransferAuditEvent] = Field(default_factory=list)
    notes: str


class LedgerAccountsResponse(BaseModel):
    isolation_level: str
    isolation_reason: str
    accounts: list[LedgerAccountView]


class IntegrityAgentResult(BaseModel):
    """Integrity findings only. This is not a final investigation report."""

    question: str
    report: IntegrityReport
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)


class RiskWhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: str = Field(pattern=r"^(card|upi|netbanking|wallet)$")
    amount_cents: int = Field(gt=0, le=10_000_000)
    hour: int | None = Field(default=None, ge=0, le=23)
    weekday: int | None = Field(default=None, ge=0, le=6)
    prior_fail_rate: float | None = Field(default=None, ge=0, le=1)


class RiskWhatIfScore(BaseModel):
    merchant_id: str
    method_id: str
    amount_cents: int
    risk_probability: float = Field(ge=0, le=1)
    risk_class: Literal["LOW", "MEDIUM", "HIGH"]
    expected_loss_cents: int
    currency: str = "INR"
    contributions: list[RiskContribution] = Field(default_factory=list)
    next_action: Literal["monitor", "investigate"]
    notes: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    version: str
    database: Literal["up"]
