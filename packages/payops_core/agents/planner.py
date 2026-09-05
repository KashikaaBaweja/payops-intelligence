from __future__ import annotations

import re
from datetime import datetime

from payops_core.data.synthetic_generator import INCIDENT_UPI_SPIKE, INCIDENT_WEBHOOK_DELAY
from payops_core.ml.select import select_ml_task
from payops_core.models.schemas import InvestigationPlan, Task, TimeWindow
from payops_core.rag.glossary import expand_query

_MERCHANT = re.compile(r"\bM\d{3}\b", re.I)
_DOC_HINTS = frozenset(
    {
        "mean",
        "meaning",
        "lifecycle",
        "policy",
        "runbook",
        "docs",
        "documentation",
        "gateway_timeout",
        "error",
        "refund",
    }
)
_METRIC_HINTS = frozenset(
    {
        "rate",
        "success",
        "failure",
        "failed",
        "fail",
        "metric",
        "metrics",
        "breakdown",
        "compare",
        "spike",
        "drop",
        "volume",
    }
)
_HEALTH_HINTS = frozenset({"health", "healthy", "scorecard"})
_WEBHOOK_HINTS = frozenset(
    {"webhook", "webhooks", "ack", "delayed", "duplicate", "retry", "retries"}
)
_INTEGRITY_HINTS = frozenset(
    {
        "acid",
        "integrity",
        "consistent",
        "consistency",
        "invariant",
        "invariants",
        "constraint",
        "constraints",
        "orphan",
        "orphans",
        "atomic",
        "durability",
        "durable",
        "rollback",
        "audit",
    }
)
_TOKEN = re.compile(r"[a-z0-9_]+")
DEFAULT_WINDOW = TimeWindow(start=datetime(2024, 6, 1), end=datetime(2024, 7, 1))


class PlannerAgent:
    """Deterministic investigation planner. Does not call an LLM."""

    def plan(self, question: str, merchant_id: str | None = None) -> InvestigationPlan:
        tokens = set(_TOKEN.findall(expand_query(question).lower()))
        merchants = [match.group(0).upper() for match in _MERCHANT.finditer(question)]
        merchant_id = merchants[0] if merchants else _named_merchant(question) or merchant_id
        method_id = "upi" if "upi" in tokens else None
        window = _window_for(tokens)
        tasks: list[Task] = []
        ml_task = select_ml_task(question)
        if ml_task in {"classification", "both"} and merchant_id:
            tasks.append(
                Task(
                    task_id="ml-1",
                    task_type="score_risk",
                    rationale="Question asks for payment-outcome classification.",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="ml",
                )
            )
            tasks.append(
                Task(
                    task_id="sql-risk",
                    task_type="query_metrics",
                    rationale="A classifier is a signal. Investigate observed failure metrics.",
                    query=question,
                    merchant_id=merchant_id,
                    method_id=method_id,
                    evidence_category="metric",
                )
            )
        if ml_task in {"regression", "both"} and merchant_id:
            tasks.append(
                Task(
                    task_id="ml-reg-1",
                    task_type="score_regression",
                    rationale="Question asks for a numeric prediction (capture latency).",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="ml",
                )
            )
        if tokens & _HEALTH_HINTS and merchant_id:
            tasks.append(
                Task(
                    task_id="health-1",
                    task_type="merchant_health",
                    rationale="Question asks for an explainable merchant health score.",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="health",
                )
            )
        if tokens & _INTEGRITY_HINTS:
            tasks.append(
                Task(
                    task_id="integrity-1",
                    task_type="validate_integrity",
                    rationale="Question asks for payment/order consistency or ACID invariants.",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="integrity",
                )
            )
        if tokens & _WEBHOOK_HINTS:
            tasks.append(
                Task(
                    task_id="wh-1",
                    task_type="inspect_webhooks",
                    rationale="Question references webhook delivery.",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="webhook",
                )
            )
        if tokens & _METRIC_HINTS or (merchant_id and "investigate" in tokens):
            if not any(task.task_type == "query_metrics" for task in tasks):
                tasks.append(
                    Task(
                        task_id="sql-1",
                        task_type="query_metrics",
                        rationale="Question needs payment metrics.",
                        query=question,
                        merchant_id=merchant_id,
                        method_id=method_id,
                        evidence_category="metric",
                    )
                )
        if tokens & _DOC_HINTS or not tasks:
            tasks.append(
                Task(
                    task_id="doc-1",
                    task_type="retrieve_docs",
                    rationale="Question needs documentation evidence.",
                    query=question,
                    merchant_id=merchant_id,
                    evidence_category="doc",
                )
            )
        return InvestigationPlan(
            goal=question,
            merchant_id=merchant_id,
            time_window=window,
            tasks=tasks,
        )


def _named_merchant(question: str) -> str | None:
    lowered = question.lower()
    if "harbor" in lowered:
        return "M102"
    if "cedar" in lowered:
        return "M201"
    return None


def _window_for(tokens: set[str]) -> TimeWindow:
    if tokens & {"webhook", "webhooks", "ack", "delayed"}:
        return TimeWindow(
            start=INCIDENT_WEBHOOK_DELAY["start"],
            end=INCIDENT_WEBHOOK_DELAY["end"],
        )
    if tokens & {"upi", "gateway_timeout", "timeout"}:
        return TimeWindow(
            start=INCIDENT_UPI_SPIKE["start"],
            end=INCIDENT_UPI_SPIKE["end"],
        )
    return DEFAULT_WINDOW
