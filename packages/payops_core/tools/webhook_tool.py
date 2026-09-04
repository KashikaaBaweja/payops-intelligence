from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from payops_core.data.db import make_engine
from payops_core.models import EvidenceItem, TimeWindow


class WebhookTool:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or make_engine()

    def get_delivery_failures(
        self, merchant_id: str, window: TimeWindow | None = None
    ) -> list[EvidenceItem]:
        params: dict[str, Any] = {"merchant_id": merchant_id}
        clauses = ["p.merchant_id = :merchant_id"]
        if window:
            clauses.append("w.created_at >= :start AND w.created_at < :end")
            params["start"] = window.start.strftime("%Y-%m-%d %H:%M:%S")
            params["end"] = window.end.strftime("%Y-%m-%d %H:%M:%S")
        where = " AND ".join(clauses)
        sql = f"""
            SELECT w.delivery_status, COUNT(*) AS n, AVG(w.delay_ms) AS avg_delay
            FROM webhook_events w
            JOIN payments p ON p.payment_id = w.payment_id
            WHERE {where}
            GROUP BY w.delivery_status
        """
        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        items = []
        for row in rows:
            items.append(
                EvidenceItem(
                    evidence_id=f"wh-{merchant_id}-{row['delivery_status']}",
                    source="webhook",
                    text_snippet=(
                        f"Webhook {row['delivery_status']}: count={row['n']}, "
                        f"avg_delay_ms={round(row['avg_delay'] or 0)}"
                    ),
                    metadata=dict(row),
                )
            )
        return items

    def find_delayed_events(
        self, merchant_id: str, threshold_ms: int = 30000, window: TimeWindow | None = None
    ) -> EvidenceItem:
        params: dict[str, Any] = {"merchant_id": merchant_id, "threshold": threshold_ms}
        clauses = ["p.merchant_id = :merchant_id", "w.delay_ms >= :threshold"]
        if window:
            clauses.append("w.created_at >= :start AND w.created_at < :end")
            params["start"] = window.start.strftime("%Y-%m-%d %H:%M:%S")
            params["end"] = window.end.strftime("%Y-%m-%d %H:%M:%S")
        sql = f"""
            SELECT COUNT(*) AS n, AVG(w.delay_ms) AS avg_delay
            FROM webhook_events w
            JOIN payments p ON p.payment_id = w.payment_id
            WHERE {" AND ".join(clauses)}
        """
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), params).mappings().one()
        return EvidenceItem(
            evidence_id=f"wh-delay-{merchant_id}",
            source="webhook",
            text_snippet=(
                f"{row['n']} delayed webhook deliveries (>= {threshold_ms}ms), "
                f"avg_delay_ms={round(row['avg_delay'] or 0)}"
            ),
            metadata=dict(row),
        )
