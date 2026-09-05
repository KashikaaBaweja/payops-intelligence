from pathlib import Path

from fastapi.testclient import TestClient
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.ml.train import clear_model_cache

from apps.api.deps import get_session
from apps.api.main import create_app


def _client(tmp_path: Path) -> tuple[TestClient, object]:
    clear_model_cache()
    url = f"sqlite:///{tmp_path / 'payops.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    session = session_factory(engine)()

    def override_session():
        yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session


def test_merchant_risk_endpoint(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    response = client.get(
        "/merchants/M102/risk",
        params={"start": "2024-06-01T00:00:00", "end": "2024-07-01T00:00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["merchant_id"] == "M102"
    assert body["sample_size"] > 0
    assert set(body["quality"]) >= {
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "positive_support",
        "confusion_matrix",
    }
    assert "regression_rmse" not in body["quality"]
    assert body["prediction"] in {"failed", "succeeded"}
    assert body["card"]["task"] == "classification"
    assert set(body["quality"]["confusion_matrix"]) == {
        "true_negative",
        "false_positive",
        "false_negative",
        "true_positive",
    }
    assert "fraud decision" in body["notes"].lower()
    alias = client.get(
        "/merchants/M102/ml/classification",
        params={"start": "2024-06-01T00:00:00", "end": "2024-07-01T00:00:00"},
    )
    assert alias.status_code == 200
    assert alias.json()["merchant_id"] == "M102"
    session.close()


def test_merchant_regression_endpoint(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    response = client.get(
        "/merchants/M102/ml/regression",
        params={"start": "2024-06-01T00:00:00", "end": "2024-07-01T00:00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["merchant_id"] == "M102"
    assert body["target"] == "capture_latency_seconds"
    assert set(body["quality"]) >= {"mae", "rmse", "r2", "test_size"}
    assert body["card"]["task"] == "regression"
    session.close()


def test_what_if_endpoint(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    response = client.post(
        "/merchants/M102/risk/what-if",
        json={"method_id": "upi", "amount_cents": 48500, "prior_fail_rate": 0.5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method_id"] == "upi"
    assert body["amount_cents"] == 48500
    assert body["next_action"] in {"monitor", "investigate"}
    session.close()


def test_what_if_rejects_raw_sql_field(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    response = client.post(
        "/merchants/M102/risk/what-if",
        json={"method_id": "upi", "amount_cents": 1000, "sql": "DROP TABLE payments"},
    )
    assert response.status_code == 422
    session.close()


def test_risk_unknown_merchant(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    response = client.get("/merchants/M999/risk")
    assert response.status_code == 404
    session.close()
