from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal[
    "documentation-only",
    "sql-required",
    "webhook-required",
    "multi-source",
    "insufficient-evidence",
    "ambiguous-question",
    "conflicting-evidence",
    "anomaly-investigation",
]


class InjectedHypothesis(BaseModel):
    cause: str
    confidence: float = 0.95
    category: str = "processor"


class EvalCase(BaseModel):
    """One labeled investigation question and the behavior the harness should check."""

    id: str
    category: Category
    question: str
    expected_behavior: str
    expected_tools: list[str]
    forbidden_tools: list[str] = Field(default_factory=list)
    relevant_doc_ids: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    expected_sufficient: bool | None = None
    expect_refine: bool | None = None
    expect_unsupported: bool = False
    max_iterations: int | None = None
    inject_hypothesis: InjectedHypothesis | None = None


class MetricScore(BaseModel):
    name: str
    score: float | None
    detail: str = ""
    applicable: bool = True


class CaseResult(BaseModel):
    case_id: str
    category: Category
    question: str
    expected_behavior: str
    passed: bool
    metrics: list[MetricScore]
    planned_tools: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    iteration: int = 0
    evidence_sufficient: bool | None = None
    notes: list[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    case_count: int
    passed: int
    failed: int
    pass_rate: float
    metric_means: dict[str, float]
    category_pass_rate: dict[str, float]
    cases: list[CaseResult]
    extra: dict[str, Any] = Field(default_factory=dict)
