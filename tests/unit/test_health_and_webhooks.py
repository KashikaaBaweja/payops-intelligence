from datetime import datetime

from payops_core.data.db import apply_schema, make_engine
from payops_core.data.synthetic_generator import generate
from payops_core.models import TimeWindow
from payops_core.tools.merchant_health import merchant_health
from payops_core.tools.webhook_tool import WebhookTool


def test_health_score_is_explainable():
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    generate(engine, seed=42)
    item = merchant_health("M101", engine=engine)
    components = item.metadata["components"]
    assert "success_rate" in components
    assert "weights" in components
    assert 0 <= item.metadata["score"] <= 1


def test_webhook_delay_incident_is_visible():
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    generate(engine, seed=42)
    tool = WebhookTool(engine)
    window = TimeWindow(start=datetime(2024, 6, 18, 14, 0, 0), end=datetime(2024, 6, 18, 16, 0, 0))
    delayed = tool.find_delayed_events("M201", window=window)
    assert (delayed.metadata.get("n") or 0) > 0
