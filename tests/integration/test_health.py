from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body
    assert body["version"]


def test_ready_endpoint_sqlite() -> None:
    client = TestClient(create_app())
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_ready_endpoint_unavailable(monkeypatch) -> None:
    from payops_core.config import get_settings

    monkeypatch.setenv(
        "PAYOPS_DATABASE_URL",
        "postgresql+psycopg://payops:payops@127.0.0.1:9/missing",
    )
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["detail"] == "database unavailable"
    finally:
        get_settings.cache_clear()
