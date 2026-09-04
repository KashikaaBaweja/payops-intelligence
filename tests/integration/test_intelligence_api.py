from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from payops_core.data.engine import make_engine
from payops_core.data.seed import seed
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

from apps.api.main import create_app
from apps.api.store import InvestigationStore
from tests.health_fixtures import HEALTH_WINDOW

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"


@pytest.fixture(scope="module")
def api_client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("api") / "payops.db"
    url = f"sqlite:///{db_path}"
    seed(url, rng_seed=42)
    store, _count = ingest_corpus(CORPUS, store=InMemoryVectorStore())
    engine = make_engine(url)
    app = create_app()
    app.state.engine = engine
    app.state.retriever = DocumentRetriever(store)
    app.state.investigations = InvestigationStore()
    with TestClient(app) as client:
        yield client


def test_openapi_documents_required_paths(api_client) -> None:
    schema = api_client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in (
        "/investigations",
        "/investigations/{id}",
        "/investigations/{id}/trace",
        "/merchants/{id}/health",
        "/merchants/{id}/metrics",
        "/evidence/{id}",
        "/health",
    ):
        assert path in paths
    post = paths["/investigations"]["post"]
    assert "InvestigationCreateRequest" in str(schema["components"]["schemas"])
    assert post["responses"]["201"]


def test_request_id_is_echoed(api_client) -> None:
    response = api_client.get("/health", headers={"X-Request-ID": "req-test-1"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test-1"


def test_request_id_is_generated_when_missing(api_client) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_create_get_investigation_and_trace(api_client) -> None:
    created = api_client.post(
        "/investigations",
        json={"question": "What is the payment lifecycle?", "max_iterations": 2},
    )
    assert created.status_code == 201
    body = created.json()
    investigation_id = body["investigation_id"]
    assert body["status"] == "completed"
    assert body["report"]["executive_summary"]
    assert created.headers["Location"] == f"/investigations/{investigation_id}"

    fetched = api_client.get(f"/investigations/{investigation_id}")
    assert fetched.status_code == 200
    assert fetched.json()["investigation_id"] == investigation_id
    assert fetched.json()["report"]["incident_id"]

    trace = api_client.get(f"/investigations/{investigation_id}/trace")
    assert trace.status_code == 200
    events = trace.json()["events"]
    assert events
    assert {event["node"] for event in events} >= {"planner", "writer"}
    assert all("reasoning" not in event for event in events)

    evidence_id = body["report"]["evidence"][0]["evidence_id"]
    evidence = api_client.get(f"/evidence/{evidence_id}")
    assert evidence.status_code == 200
    assert evidence.json()["evidence_id"] == evidence_id
    assert evidence.json()["text_snippet"]


def test_investigation_validation_and_not_found(api_client) -> None:
    empty = api_client.post("/investigations", json={"question": "no"})
    assert empty.status_code == 422
    assert empty.json()["error"] == "validation_error"
    assert empty.json()["request_id"]

    extra = api_client.post(
        "/investigations",
        json={"question": "What is the payment lifecycle?", "api_key": "secret"},
    )
    assert extra.status_code == 422

    missing = api_client.get("/investigations/abc123def456")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    assert missing.json()["status_code"] == 404


def test_unknown_merchant_on_investigation(api_client) -> None:
    response = api_client.post(
        "/investigations",
        json={"question": "What is the payment lifecycle?", "merchant_id": "M999"},
    )
    assert response.status_code == 404


def test_merchant_metrics_and_health(api_client) -> None:
    params = {
        "start": HEALTH_WINDOW.start.isoformat(),
        "end": HEALTH_WINDOW.end.isoformat(),
    }
    metrics = api_client.get("/merchants/M102/metrics", params=params)
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["merchant_id"] == "M102"
    assert body["metrics"]
    names = {item["metric"] for item in body["metrics"]}
    assert "success_rate" in names
    evidence_id = "metric-get_success_rate-M102"
    evidence = api_client.get(f"/evidence/{evidence_id}")
    assert evidence.status_code == 200

    health = api_client.get("/merchants/M102/health", params=params)
    assert health.status_code == 200
    assert health.json()["score"] >= 0
    assert set(health.json()["factor_values"]) >= {
        "success_rate",
        "failure_rate",
        "refund_rate",
        "dispute_rate",
        "webhook_reliability",
        "anomaly_severity",
    }


def test_merchant_metrics_rejects_unknown_operation(api_client) -> None:
    response = api_client.get(
        "/merchants/M102/metrics",
        params={"operation": "drop_table"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_merchant_and_evidence_not_found(api_client) -> None:
    assert api_client.get("/merchants/M999/health").status_code == 404
    assert api_client.get("/merchants/M999/metrics").status_code == 404
    missing = api_client.get("/evidence/doc-does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"


def test_invalid_window_and_id(api_client) -> None:
    response = api_client.get(
        "/merchants/M102/metrics",
        params={"start": "2024-06-15T12:00:00", "end": "2024-06-15T10:00:00"},
    )
    assert response.status_code == 400
    invalid = api_client.get("/merchants/not.valid/health")
    assert invalid.status_code == 400
