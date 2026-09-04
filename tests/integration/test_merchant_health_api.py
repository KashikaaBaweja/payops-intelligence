from fastapi.testclient import TestClient
from payops_core.data.engine import create_schema, make_engine, session_factory

from apps.api.deps import get_session
from apps.api.main import create_app
from tests.health_fixtures import HEALTH_WINDOW, load_health_dataset


def _client() -> tuple[TestClient, object]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_health_dataset(session)
    session.commit()

    def override_session():
        yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session


def test_merchant_health_endpoint_returns_explainable_score() -> None:
    client, session = _client()
    response = client.get(
        "/merchants/M801/health",
        params={
            "start": HEALTH_WINDOW.start.isoformat(),
            "end": HEALTH_WINDOW.end.isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["merchant_id"] == "M801"
    assert body["band"] == "healthy"
    assert body["score"] >= 80
    assert set(body["factor_values"]) == {
        "success_rate",
        "failure_rate",
        "refund_rate",
        "dispute_rate",
        "webhook_reliability",
        "anomaly_severity",
    }
    assert body["factors"]
    assert body["penalties"] == []
    assert body["positive_signals"]
    assert body["recommendations"]
    session.close()


def test_merchant_health_endpoint_bands() -> None:
    client, session = _client()
    params = {
        "start": HEALTH_WINDOW.start.isoformat(),
        "end": HEALTH_WINDOW.end.isoformat(),
    }
    degraded = client.get("/merchants/M802/health", params=params).json()
    critical = client.get("/merchants/M803/health", params=params).json()
    assert degraded["band"] == "degraded"
    assert critical["band"] == "critical"
    assert critical["penalties"]
    session.close()


def test_merchant_health_unknown_merchant() -> None:
    client, session = _client()
    response = client.get("/merchants/M999/health")
    assert response.status_code == 404
    session.close()
