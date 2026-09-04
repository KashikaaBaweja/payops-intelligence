from __future__ import annotations

import re
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from payops_core.data.models import Dispute, Payment, Refund, WebhookEvent
from payops_core.models.schemas import AnalyticsRequest, MetricResult, TimeWindow

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ALLOWED_OPERATIONS: frozenset[str] = frozenset(
    {
        "get_success_rate",
        "get_failure_rate",
        "breakdown_by_method",
        "breakdown_by_error_code",
        "compare_time_windows",
        "compare_merchants",
        "get_refund_rate",
        "get_dispute_rate",
        "get_webhook_failure_rate",
    }
)


class SqlToolGateway:
    """Read-only catalog of parameterized analytics queries. No raw SQL input."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._handlers: dict[str, Callable[[AnalyticsRequest], MetricResult]] = {
            "get_success_rate": self._success_rate,
            "get_failure_rate": self._failure_rate,
            "breakdown_by_method": self._method_breakdown,
            "breakdown_by_error_code": self._error_breakdown,
            "compare_time_windows": self._compare_windows,
            "compare_merchants": self._compare_merchants,
            "get_refund_rate": self._refund_rate,
            "get_dispute_rate": self._dispute_rate,
            "get_webhook_failure_rate": self._webhook_failure_rate,
        }

    def run(self, request: AnalyticsRequest) -> MetricResult:
        if request.operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"Unknown analytical operation: {request.operation}")
        _validate_id(request.merchant_id, "merchant_id")
        _validate_id(request.method_id, "method_id")
        _validate_id(request.compare_merchant_id, "compare_merchant_id")
        if request.window.end <= request.window.start:
            raise ValueError("time window end must be after start")
        return self._handlers[request.operation](request)

    def _success_rate(self, request: AnalyticsRequest) -> MetricResult:
        counts = self._payment_counts(request, request.window, request.merchant_id)
        return self._rate_result(
            request,
            metric="success_rate",
            value=_ratio(counts["succeeded"], counts["total"]),
            sample_size=counts["total"],
            source="payments",
        )

    def _failure_rate(self, request: AnalyticsRequest) -> MetricResult:
        counts = self._payment_counts(request, request.window, request.merchant_id)
        return self._rate_result(
            request,
            metric="failure_rate",
            value=_ratio(counts["failed"], counts["total"]),
            sample_size=counts["total"],
            source="payments",
        )

    def _method_breakdown(self, request: AnalyticsRequest) -> MetricResult:
        rows = self.session.execute(
            select(Payment.method_id, Payment.status, func.count())
            .where(*self._payment_predicates(request, request.window, request.merchant_id))
            .group_by(Payment.method_id, Payment.status)
        ).all()
        grouped: dict[str, dict[str, int]] = {}
        for method_id, status, count in rows:
            bucket = grouped.setdefault(method_id, {"succeeded": 0, "failed": 0, "total": 0})
            bucket["total"] += int(count)
            if status in {"succeeded", "failed"}:
                bucket[status] += int(count)
        value = {
            method_id: {
                **counts,
                "success_rate": _ratio(counts["succeeded"], counts["total"]),
                "failure_rate": _ratio(counts["failed"], counts["total"]),
            }
            for method_id, counts in sorted(grouped.items())
        }
        return self._rate_result(
            request,
            metric="payment_method_breakdown",
            value=value,
            sample_size=sum(item["total"] for item in grouped.values()),
            source="payments",
            unit="breakdown",
        )

    def _error_breakdown(self, request: AnalyticsRequest) -> MetricResult:
        predicates = self._payment_predicates(request, request.window, request.merchant_id)
        predicates.append(Payment.status == "failed")
        rows = self.session.execute(
            select(Payment.error_code, func.count()).where(*predicates).group_by(Payment.error_code)
        ).all()
        total = sum(int(count) for _code, count in rows)
        value = {
            str(code): {"count": int(count), "share": _ratio(int(count), total)}
            for code, count in rows
            if code is not None
        }
        return self._rate_result(
            request,
            metric="error_code_breakdown",
            value=value,
            sample_size=total,
            source="payments",
            unit="breakdown",
        )

    def _compare_windows(self, request: AnalyticsRequest) -> MetricResult:
        previous = request.previous_window or _equal_previous(request.window)
        if previous.end <= previous.start:
            raise ValueError("previous window end must be after start")
        current = self._metric_rate(request, request.window, request.merchant_id)
        prior = self._metric_rate(request, previous, request.merchant_id)
        return self._rate_result(
            request,
            metric="time_window_comparison",
            value={
                "current": current,
                "previous": prior,
                "delta": round(current - prior, 6),
                "compare_metric": request.compare_metric,
            },
            sample_size=None,
            source="payments",
            unit="comparison",
            extra_filters={"previous_window": _window_filters(previous)},
        )

    def _compare_merchants(self, request: AnalyticsRequest) -> MetricResult:
        if not request.merchant_id or not request.compare_merchant_id:
            raise ValueError("compare_merchants requires merchant_id and compare_merchant_id")
        left = self._metric_rate(request, request.window, request.merchant_id)
        right = self._metric_rate(request, request.window, request.compare_merchant_id)
        return self._rate_result(
            request,
            metric="merchant_comparison",
            value={
                request.merchant_id: left,
                request.compare_merchant_id: right,
                "delta": round(left - right, 6),
                "compare_metric": request.compare_metric,
            },
            sample_size=None,
            source="payments",
            unit="comparison",
            extra_filters={"compare_merchant_id": request.compare_merchant_id},
        )

    def _refund_rate(self, request: AnalyticsRequest) -> MetricResult:
        succeeded = self._payment_counts(request, request.window, request.merchant_id)["succeeded"]
        refunds = self._related_count(Refund, request)
        return self._rate_result(
            request,
            metric="refund_rate",
            value=_ratio(refunds, succeeded),
            sample_size=succeeded,
            source="refunds",
            notes="processed refunds divided by succeeded payments in the window",
        )

    def _dispute_rate(self, request: AnalyticsRequest) -> MetricResult:
        succeeded = self._payment_counts(request, request.window, request.merchant_id)["succeeded"]
        disputes = self._related_count(Dispute, request)
        return self._rate_result(
            request,
            metric="dispute_rate",
            value=_ratio(disputes, succeeded),
            sample_size=succeeded,
            source="disputes",
            notes="disputes divided by succeeded payments in the window",
        )

    def _webhook_failure_rate(self, request: AnalyticsRequest) -> MetricResult:
        predicates = self._payment_predicates(request, request.window, request.merchant_id)
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(WebhookEvent)
                .join(Payment, Payment.payment_id == WebhookEvent.payment_id)
                .where(*predicates)
            )
            or 0
        )
        failed = (
            self.session.scalar(
                select(func.count())
                .select_from(WebhookEvent)
                .join(Payment, Payment.payment_id == WebhookEvent.payment_id)
                .where(*predicates, WebhookEvent.delivery_status == "failed")
            )
            or 0
        )
        return self._rate_result(
            request,
            metric="webhook_failure_rate",
            value=_ratio(int(failed), int(total)),
            sample_size=int(total),
            source="webhook_events",
        )

    def _metric_rate(
        self,
        request: AnalyticsRequest,
        window: TimeWindow,
        merchant_id: str | None,
    ) -> float:
        counts = self._payment_counts(request, window, merchant_id)
        if request.compare_metric == "failure_rate":
            return _ratio(counts["failed"], counts["total"])
        return _ratio(counts["succeeded"], counts["total"])

    def _payment_counts(
        self,
        request: AnalyticsRequest,
        window: TimeWindow,
        merchant_id: str | None,
    ) -> dict[str, int]:
        predicates = self._payment_predicates(request, window, merchant_id)
        total = (
            self.session.scalar(select(func.count()).select_from(Payment).where(*predicates)) or 0
        )
        succeeded = (
            self.session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(*predicates, Payment.status == "succeeded")
            )
            or 0
        )
        failed = (
            self.session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(*predicates, Payment.status == "failed")
            )
            or 0
        )
        return {"total": int(total), "succeeded": int(succeeded), "failed": int(failed)}

    def _related_count(self, model: type[Refund] | type[Dispute], request: AnalyticsRequest) -> int:
        predicates = [
            model.created_at >= request.window.start,
            model.created_at < request.window.end,
        ]
        stmt = select(func.count()).select_from(model).join(Payment)
        predicates.extend(self._payment_predicates(request, request.window, request.merchant_id))
        if model is Refund:
            predicates.append(Refund.status == "processed")
        return int(self.session.scalar(stmt.where(*predicates)) or 0)

    def _payment_predicates(
        self,
        request: AnalyticsRequest,
        window: TimeWindow,
        merchant_id: str | None,
    ) -> list[Any]:
        predicates: list[Any] = [
            Payment.created_at >= window.start,
            Payment.created_at < window.end,
        ]
        if merchant_id:
            predicates.append(Payment.merchant_id == merchant_id)
        if request.method_id:
            predicates.append(Payment.method_id == request.method_id)
        return predicates

    def _rate_result(
        self,
        request: AnalyticsRequest,
        *,
        metric: str,
        value: float | dict[str, Any],
        sample_size: int | None,
        source: str,
        unit: str = "ratio",
        notes: str | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> MetricResult:
        filters = {
            "merchant_id": request.merchant_id,
            "method_id": request.method_id,
            **(extra_filters or {}),
        }
        return MetricResult(
            metric=metric,
            value=value,
            window=request.window,
            filters={key: item for key, item in filters.items() if item is not None},
            tool="sql_gateway",
            source=source,
            operation=request.operation,
            merchant_id=request.merchant_id,
            unit=unit,
            notes=(notes or "no rows in window") if sample_size == 0 else notes,
            sample_size=sample_size,
        )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _equal_previous(window: TimeWindow) -> TimeWindow:
    delta = window.end - window.start
    return TimeWindow(start=window.start - delta, end=window.start)


def _window_filters(window: TimeWindow) -> dict[str, str]:
    return {"start": window.start.isoformat(), "end": window.end.isoformat()}


def _validate_id(value: str | None, field: str) -> None:
    if value is None:
        return
    if not _ID.match(value):
        raise ValueError(f"invalid {field}")
