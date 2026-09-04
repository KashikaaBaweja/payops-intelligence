from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class MetricResult(BaseModel):
    operation: str
    merchant_id: str | None = None
    window: TimeWindow | None = None
    value: float | dict[str, Any]
    unit: str = "ratio"
    notes: str | None = None


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
