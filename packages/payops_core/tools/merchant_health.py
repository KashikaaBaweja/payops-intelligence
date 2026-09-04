from sqlalchemy.engine import Engine

from payops_core.models import EvidenceItem, TimeWindow
from payops_core.tools.sql_gateway import SqlGateway, SqlOpRequest
from payops_core.tools.webhook_tool import WebhookTool

WEIGHTS = {
    "success": 0.45,
    "refund": 0.15,
    "dispute": 0.20,
    "webhook": 0.20,
}


def merchant_health(
    merchant_id: str, window: TimeWindow | None = None, engine: Engine | None = None
) -> EvidenceItem:
    sql = SqlGateway(engine)
    webhooks = WebhookTool(engine)
    success = sql.run(SqlOpRequest(operation="get_success_rate", merchant_id=merchant_id, window=window))
    refund = sql.run(SqlOpRequest(operation="get_refund_rate", merchant_id=merchant_id, window=window))
    dispute = sql.run(SqlOpRequest(operation="get_dispute_rate", merchant_id=merchant_id, window=window))
    delayed = webhooks.find_delayed_events(merchant_id, window=window)
    delay_count = delayed.metadata.get("n") or 0
    webhook_penalty = min(delay_count / 50.0, 1.0)
    score = (
        WEIGHTS["success"] * float(success.value)
        + WEIGHTS["refund"] * (1 - float(refund.value))
        + WEIGHTS["dispute"] * (1 - min(float(dispute.value) * 20, 1.0))
        + WEIGHTS["webhook"] * (1 - webhook_penalty)
    )
    return EvidenceItem(
        evidence_id=f"health-{merchant_id}",
        source="health",
        text_snippet=f"Explainable health score={round(score, 3)} for {merchant_id}",
        metadata={
            "score": round(score, 4),
            "components": {
                "success_rate": success.value,
                "refund_rate": refund.value,
                "dispute_rate": dispute.value,
                "delayed_webhooks": delay_count,
                "weights": WEIGHTS,
            },
        },
    )
