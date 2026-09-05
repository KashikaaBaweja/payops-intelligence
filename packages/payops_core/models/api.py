from datetime import datetime, timezone
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from payops_core.models.schemas import IncidentReport, MetricResult, TimeWindow, TraceEvent
from payops_core.query_input import normalize_input_method
from payops_core.query_language import QueryLanguage, normalize_language_choice


class InvestigationCreateRequest(BaseModel):
    """Create a new investigation run.

    Typed and voice input normalize to the same ``query`` string. ``input_method``
    is observability only — the graph always runs on ``query``.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "What does GATEWAY_TIMEOUT mean?",
                    "input_method": "text",
                    "max_iterations": 3,
                }
            ]
        },
    )

    query: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Normalized research query. Preferred over question.",
    )
    question: str | None = Field(
        default=None,
        max_length=4000,
        description="Alias for query. Kept so existing clients keep working.",
    )
    input_method: Literal["text", "voice"] = Field(
        default="text",
        description="How the operator entered the query. Does not change the graph.",
    )
    language: Literal["auto", "en", "hi", "hi-latn"] = Field(
        default="auto",
        description="Speech and answer language. Auto detects from the query.",
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

    @model_validator(mode="before")
    @classmethod
    def accept_query_or_question(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("query")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raw = data.get("question")
        if isinstance(raw, str):
            raw = raw.strip()
        data["query"] = raw
        data["question"] = raw
        data["input_method"] = normalize_input_method(data.get("input_method"))
        data["language"] = normalize_language_choice(data.get("language"))
        return data

    @model_validator(mode="after")
    def mirror_normalized_query(self) -> Self:
        self.question = self.query
        return self


class InvestigationResponse(BaseModel):
    investigation_id: str
    status: Literal["completed", "failed"]
    question: str
    original_query: str | None = None
    input_method: Literal["text", "voice"] = "text"
    query_language: QueryLanguage = "en"
    response_language: QueryLanguage = "en"
    retrieval_query: str | None = None
    created_at: datetime
    report: IncidentReport | None = None
    error: str | None = None
    duration_ms: int | None = None


class InvestigationSummary(BaseModel):
    investigation_id: str
    question: str
    status: Literal["completed", "failed"]
    created_at: datetime
    merchant_id: str | None = None
    confidence: float | None = None
    evidence_sufficient: bool | None = None
    input_method: Literal["text", "voice"] = "text"
    duration_ms: int | None = None
    query_language: QueryLanguage = "en"


class InvestigationListResponse(BaseModel):
    items: list[InvestigationSummary] = Field(default_factory=list)
    total: int = 0


class InvestigationDeleteResponse(BaseModel):
    deleted: int = 0


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
