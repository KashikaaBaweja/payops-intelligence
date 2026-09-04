from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class Task(BaseModel):
    task_id: str
    task_type: Literal[
        "retrieve_docs",
        "query_metrics",
        "inspect_webhooks",
        "compare_merchants",
        "merchant_health",
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
    source: Literal["doc", "metric", "webhook", "health"]
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


class ResearcherResult(BaseModel):
    """Retrieved evidence only. This is not a final investigation answer."""

    question: str
    queries: list[SearchQuery] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    rejected_count: int = 0


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
            evidence_id=f"metric-{self.operation}-{self.merchant_id or 'all'}",
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
            evidence_id=f"health-{self.merchant_id}",
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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    version: str
    database: Literal["up"]
