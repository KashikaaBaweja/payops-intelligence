from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from payops_core.data.db import make_engine
from payops_core.models import MetricResult, TimeWindow

ALLOWED_OPS = {
    "get_success_rate",
    "get_failure_rate",
    "breakdown_by_error_code",
    "breakdown_by_method",
    "compare_windows",
    "get_refund_rate",
    "get_dispute_rate",
}


class SqlOpRequest(BaseModel):
    operation: Literal[
        "get_success_rate",
        "get_failure_rate",
        "breakdown_by_error_code",
        "breakdown_by_method",
        "compare_windows",
        "get_refund_rate",
        "get_dispute_rate",
    ]
    merchant_id: str | None = None
    method_id: str | None = None
    window: TimeWindow | None = None
    compare_window: TimeWindow | None = None


class SqlGateway:
    """Fixed catalog of parameterized queries. Agents never generate SQL."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or make_engine()

    def run(self, request: SqlOpRequest) -> MetricResult:
        if request.operation not in ALLOWED_OPS:
            raise ValueError(f"Operation not allowed: {request.operation}")
        handler = getattr(self, request.operation)
        value = handler(request)
        return MetricResult(
            operation=request.operation,
            merchant_id=request.merchant_id,
            window=request.window,
            value=value,
        )

    def _filters(self, request: SqlOpRequest) -> tuple[str, dict[str, Any]]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if request.merchant_id:
            clauses.append("merchant_id = :merchant_id")
            params["merchant_id"] = request.merchant_id
        if request.method_id:
            clauses.append("method_id = :method_id")
            params["method_id"] = request.method_id
        if request.window:
            clauses.append("created_at >= :start AND created_at < :end")
            params["start"] = request.window.start.strftime("%Y-%m-%d %H:%M:%S")
            params["end"] = request.window.end.strftime("%Y-%m-%d %H:%M:%S")
        return " AND ".join(clauses), params

    def _rate(self, request: SqlOpRequest, status: str | None = None) -> float:
        where, params = self._filters(request)
        sql = f"SELECT COUNT(*) FROM payments WHERE {where}"
        if status:
            sql += " AND status = :status"
            params["status"] = status
        with self.engine.begin() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM payments WHERE {where}"), params
            ).scalar_one()
            matched = conn.execute(text(sql), params).scalar_one() if status else total
        if not total:
            return 0.0
        return round(matched / total, 4)

    def get_success_rate(self, request: SqlOpRequest) -> float:
        return self._rate(request, "succeeded")

    def get_failure_rate(self, request: SqlOpRequest) -> float:
        return self._rate(request, "failed")

    def breakdown_by_error_code(self, request: SqlOpRequest) -> dict[str, Any]:
        where, params = self._filters(request)
        sql = f"""
            SELECT error_code, COUNT(*) AS n
            FROM payments
            WHERE {where} AND status = 'failed' AND error_code IS NOT NULL
            GROUP BY error_code
            ORDER BY n DESC
            LIMIT 20
        """
        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return {row["error_code"]: row["n"] for row in rows}

    def breakdown_by_method(self, request: SqlOpRequest) -> dict[str, Any]:
        where, params = self._filters(request)
        sql = f"""
            SELECT method_id,
                   SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS success_rate,
                   COUNT(*) AS n
            FROM payments
            WHERE {where}
            GROUP BY method_id
        """
        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return {
            row["method_id"]: {"success_rate": round(row["success_rate"], 4), "n": row["n"]}
            for row in rows
        }

    def compare_windows(self, request: SqlOpRequest) -> dict[str, Any]:
        current = self.get_success_rate(request)
        if not request.compare_window:
            return {"current": current, "baseline": None, "delta": None}
        baseline_req = request.model_copy(update={"window": request.compare_window})
        baseline = self.get_success_rate(baseline_req)
        return {"current": current, "baseline": baseline, "delta": round(current - baseline, 4)}

    def _joined_rate(self, request: SqlOpRequest, table: str, alias: str) -> float:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if request.merchant_id:
            clauses.append("p.merchant_id = :merchant_id")
            params["merchant_id"] = request.merchant_id
        if request.method_id:
            clauses.append("p.method_id = :method_id")
            params["method_id"] = request.method_id
        if request.window:
            clauses.append("p.created_at >= :start AND p.created_at < :end")
            params["start"] = request.window.start.strftime("%Y-%m-%d %H:%M:%S")
            params["end"] = request.window.end.strftime("%Y-%m-%d %H:%M:%S")
        where = " AND ".join(clauses)
        with self.engine.begin() as conn:
            related = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} {alias} "
                    f"JOIN payments p ON p.payment_id = {alias}.payment_id WHERE {where}"
                ),
                params,
            ).scalar_one()
            payments = conn.execute(
                text(f"SELECT COUNT(*) FROM payments p WHERE {where}"), params
            ).scalar_one()
        return round(related / payments, 4) if payments else 0.0

    def get_refund_rate(self, request: SqlOpRequest) -> float:
        return self._joined_rate(request, "refunds", "r")

    def get_dispute_rate(self, request: SqlOpRequest) -> float:
        return self._joined_rate(request, "disputes", "d")
