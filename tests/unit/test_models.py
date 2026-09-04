from datetime import datetime, timezone

from payops_core.models import HealthResponse, Hypothesis, IncidentReport, TimeWindow


def test_time_window_roundtrip() -> None:
    window = TimeWindow(
        start=datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc),
        end=datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    assert window.end > window.start


def test_incident_report_requires_cause() -> None:
    report = IncidentReport(
        executive_summary="placeholder",
        incident_id="INV-1",
        severity="low",
        likely_cause=Hypothesis(cause="unknown", supporting_evidence_ids=[], confidence=0.2),
        confidence=0.2,
        evidence_sufficient=False,
    )
    assert report.evidence_sufficient is False


def test_health_response() -> None:
    payload = HealthResponse(status="ok", environment="local", version="0.1.0")
    assert payload.status == "ok"
