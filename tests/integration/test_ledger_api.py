from pathlib import Path

from fastapi.testclient import TestClient
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.seed import seed

from apps.api.deps import get_session
from apps.api.main import create_app


def _client(tmp_path: Path) -> tuple[TestClient, object]:
    url = f"sqlite:///{tmp_path / 'payops.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    session = session_factory(engine)()

    def override_session():
        yield session

    app = create_app()
    app.state.engine = engine
    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session


def test_transfer_commit_and_rollback_endpoints(tmp_path: Path) -> None:
    client, session = _client(tmp_path)
    accounts = client.get("/transactions/accounts")
    assert accounts.status_code == 200
    body = accounts.json()
    assert body["isolation_level"] == "IMMEDIATE"
    ids = {item["account_id"] for item in body["accounts"]}
    assert "M102-wallet" in ids
    committed = client.post(
        "/transactions/transfers",
        json={
            "from_account_id": "M102-wallet",
            "to_account_id": "M201-wallet",
            "amount_cents": 4000,
        },
    )
    assert committed.status_code == 200
    commit_body = committed.json()
    assert commit_body["status"] == "committed"
    assert commit_body["commit_or_rollback"] == "COMMIT"
    assert commit_body["transfer_id"]
    fetched = client.get(f"/transactions/transfers/{commit_body['transfer_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "committed"
    rolled = client.post(
        "/transactions/transfers",
        json={
            "from_account_id": "M102-wallet",
            "to_account_id": "M201-wallet",
            "amount_cents": 4000,
            "fail_at": "after_debit",
        },
    )
    assert rolled.status_code == 200
    roll_body = rolled.json()
    assert roll_body["status"] == "rolled_back"
    assert roll_body["failure_point"] == "after_debit"
    assert roll_body["before_balance"]["from"] == roll_body["after_balance"]["from"]
    session.close()
