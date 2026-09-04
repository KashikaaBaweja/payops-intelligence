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
    note: str | None = None


class CritiqueResult(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    revision_instructions: str | None = None


class EvidenceRef(BaseModel):
    evidence_id: str
    source: str
    label: str


class TraceEvent(BaseModel):
    step: str
    agent: str
    tool: str | None = None
    input_summary: str
    output_summary: str
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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    version: str
