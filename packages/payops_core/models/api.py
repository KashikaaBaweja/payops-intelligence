from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from payops_core.models.schemas import IncidentReport, MetricResult, TimeWindow, TraceEvent


class InvestigationCreateRequest(BaseModel):
    """Create a new investigation run."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "question": "What does GATEWAY_TIMEOUT mean?",
                    "max_iterations": 3,
                }
            ]
        },
    )

    question: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Natural-language operations question to investigate.",
    )
    merchant_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Optional merchant to validate before running the graph.",
    )
    max_iterations: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description="Optional cap on investigation loops. Defaults to server config.",
    )


class InvestigationResponse(BaseModel):
    investigation_id: str
    status: Literal["completed", "failed"]
    question: str
    created_at: datetime
    report: IncidentReport | None = None
    error: str | None = None


class InvestigationSummary(BaseModel):
    investigation_id: str
    question: str
    status: Literal["completed", "failed"]
    created_at: datetime
    merchant_id: str | None = None
    confidence: float | None = None
    evidence_sufficient: bool | None = None


class InvestigationListResponse(BaseModel):
    items: list[InvestigationSummary] = Field(default_factory=list)
    total: int = 0


class ServiceStatus(BaseModel):
    name: str
    status: Literal["ok", "down", "disabled", "degraded"]
    detail: str


class SystemHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    environment: str
    version: str
    services: list[ServiceStatus]


class CorpusDocument(BaseModel):
    document_id: str
    name: str
    kind: str
    bytes: int


class CorpusResponse(BaseModel):
    backend: str
    documents: list[CorpusDocument] = Field(default_factory=list)


class InvestigationTraceResponse(BaseModel):
    investigation_id: str
    events: list[TraceEvent] = Field(default_factory=list)


class MerchantMetricsResponse(BaseModel):
    merchant_id: str
    window: TimeWindow
    metrics: list[MetricResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    detail: str | list[Any]
    status_code: int
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
