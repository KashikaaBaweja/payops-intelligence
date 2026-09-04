from __future__ import annotations

import re

from sqlalchemy.orm import Session

from payops_core.models.schemas import (
    EvidenceBundle,
    Task,
    TimeWindow,
    WebhookInspectorResult,
    WebhookOperation,
    WebhookRequest,
)
from payops_core.tools.webhook_analysis import DELAY_THRESHOLD_MS
from payops_core.tools.webhook_gateway import ALLOWED_WEBHOOK_OPERATIONS, WebhookToolGateway

_TOKEN = re.compile(r"[a-z0-9_]+")
_MERCHANT = re.compile(r"\bM\d{3}\b", re.I)
_PAYMENT = re.compile(r"\bP(?:WH)?\d{3,}\b", re.I)
_OPERATION_HINTS: tuple[tuple[frozenset[str], WebhookOperation], ...] = (
    (frozenset({"missing", "absent", "never"}), "find_missing_events"),
    (frozenset({"delay", "delayed", "late"}), "find_delayed_events"),
    (frozenset({"failed", "failure", "undelivered"}), "get_delivery_failures"),
    (frozenset({"retry", "retries", "reattempt"}), "find_retries"),
    (frozenset({"duplicate", "duplicates", "dup"}), "find_duplicate_events"),
    (frozenset({"correlate", "correlation", "mismatch"}), "correlate_events_and_payments"),
)


class WebhookInspectorAgent:
    """Inspect webhook delivery. Does not write a final report or orchestrate other agents."""

    def __init__(self, session: Session) -> None:
        self.gateway = WebhookToolGateway(session)

    def inspect(
        self,
        question: str,
        *,
        window: TimeWindow | None = None,
        merchant_id: str | None = None,
        payment_id: str | None = None,
        delay_threshold_ms: int = DELAY_THRESHOLD_MS,
        task: Task | None = None,
    ) -> WebhookInspectorResult:
        if task is not None and task.task_type != "inspect_webhooks":
            raise ValueError("WebhookInspectorAgent only executes inspect_webhooks tasks")
        found_merchants = [match.group(0).upper() for match in _MERCHANT.finditer(question)]
        found_payments = [match.group(0).upper() for match in _PAYMENT.finditer(question)]
        if task is not None and task.merchant_id:
            merchant_id = task.merchant_id
        elif merchant_id is None and found_merchants:
            merchant_id = found_merchants[0]
        if payment_id is None and found_payments:
            payment_id = found_payments[0]
        operations = self.plan_operations(question, task, payment_id=payment_id)
        results = [
            self.gateway.run(
                WebhookRequest(
                    operation=operation,
                    window=window,
                    merchant_id=merchant_id,
                    payment_id=payment_id,
                    delay_threshold_ms=delay_threshold_ms,
                )
            )
            for operation in operations
        ]
        evidence = EvidenceBundle(
            items=[item for result in results for item in result.to_evidence_items()]
        )
        return WebhookInspectorResult(
            question=question,
            operations=operations,
            results=results,
            evidence=evidence,
        )

    def plan_operations(
        self,
        question: str,
        task: Task | None = None,
        payment_id: str | None = None,
    ) -> list[WebhookOperation]:
        planned: list[WebhookOperation] = []
        seen: set[str] = set()

        def add(operation: WebhookOperation) -> None:
            if operation not in seen:
                seen.add(operation)
                planned.append(operation)

        if task is not None and task.query and task.query in ALLOWED_WEBHOOK_OPERATIONS:
            add(task.query)  # type: ignore[arg-type]
        tokens = set(_TOKEN.findall(question.lower()))
        for needles, operation in _OPERATION_HINTS:
            if tokens & needles:
                add(operation)
        if payment_id and "get_events_for_payment" not in seen and not planned:
            add("get_events_for_payment")
        if not planned:
            add("find_delayed_events")
            add("get_delivery_failures")
            add("find_missing_events")
        return planned
