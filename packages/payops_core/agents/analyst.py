from __future__ import annotations

import re

from sqlalchemy.orm import Session

from payops_core.models.schemas import (
    AnalystResult,
    AnalyticsOperation,
    AnalyticsRequest,
    Task,
    TimeWindow,
)
from payops_core.tools.sql_gateway import ALLOWED_OPERATIONS, SqlToolGateway

_TOKEN = re.compile(r"[a-z0-9_]+")
_MERCHANT = re.compile(r"\bM\d{3}\b", re.I)
_OPERATION_HINTS: tuple[tuple[frozenset[str], AnalyticsOperation], ...] = (
    (frozenset({"success", "succeeded"}), "get_success_rate"),
    (frozenset({"failure", "failed", "fail"}), "get_failure_rate"),
    (
        frozenset({"method", "methods", "upi", "card", "wallet", "netbanking"}),
        "breakdown_by_method",
    ),
    (frozenset({"error", "errors", "gateway_timeout"}), "breakdown_by_error_code"),
    (frozenset({"refund", "refunds"}), "get_refund_rate"),
    (frozenset({"dispute", "disputes", "chargeback"}), "get_dispute_rate"),
    (frozenset({"webhook", "webhooks"}), "get_webhook_failure_rate"),
    (frozenset({"previous", "yesterday", "prior", "delta"}), "compare_time_windows"),
)


class DataAnalystAgent:
    """Run validated analytics operations. Does not write a final report."""

    def __init__(self, session: Session) -> None:
        self.gateway = SqlToolGateway(session)

    def analyze(
        self,
        question: str,
        *,
        window: TimeWindow,
        merchant_id: str | None = None,
        method_id: str | None = None,
        compare_merchant_id: str | None = None,
        previous_window: TimeWindow | None = None,
        task: Task | None = None,
    ) -> AnalystResult:
        if task is not None and task.task_type != "query_metrics":
            raise ValueError("DataAnalystAgent only executes query_metrics tasks")
        found = [match.group(0).upper() for match in _MERCHANT.finditer(question)]
        if task is not None and task.merchant_id:
            merchant_id = task.merchant_id
        elif merchant_id is None and found:
            merchant_id = found[0]
        compare_merchant_id = compare_merchant_id or (found[1] if len(found) > 1 else None)
        method_id = task.method_id if task and task.method_id else method_id
        operations = self.plan_operations(
            question,
            task,
            compare_merchant_id=compare_merchant_id,
        )
        metrics = [
            self.gateway.run(
                AnalyticsRequest(
                    operation=operation,
                    window=window,
                    merchant_id=merchant_id,
                    method_id=method_id,
                    compare_merchant_id=compare_merchant_id,
                    previous_window=previous_window,
                )
            )
            for operation in operations
        ]
        return AnalystResult(question=question, operations=operations, metrics=metrics)

    def plan_operations(
        self,
        question: str,
        task: Task | None = None,
        compare_merchant_id: str | None = None,
    ) -> list[AnalyticsOperation]:
        planned: list[AnalyticsOperation] = []
        seen: set[str] = set()

        def add(operation: AnalyticsOperation) -> None:
            if operation not in seen:
                seen.add(operation)
                planned.append(operation)

        if task is not None and task.query and task.query in ALLOWED_OPERATIONS:
            add(task.query)  # type: ignore[arg-type]
        tokens = set(_TOKEN.findall(question.lower()))
        for needles, operation in _OPERATION_HINTS:
            if tokens & needles:
                add(operation)
        if compare_merchant_id:
            add("compare_merchants")
        if not planned:
            add("get_success_rate")
            add("get_failure_rate")
        return planned
