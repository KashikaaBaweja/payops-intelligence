from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from payops_core.auth.emailer import CapturingEmailSender
from payops_core.auth.tokens import hash_token
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import AuditEvent, AuthSession
from payops_core.data.seed import seed
from sqlalchemy import select

from apps.api.main import create_app
from tests.auth_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    TEST_EMAIL,
    authenticate_client,
    insert_user,
    login,
)

SIGNUP = {
    "name": "Ada Lovelace",
    "email": "ada@payintel.test",
    "password": "Testuser1!x",
    "confirm_password": "Testuser1!x",
}


def _app(tmp_path, sender=None):
    url = f"sqlite:///{tmp_path / 'auth.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    app = create_app()
    app.state.engine = engine
    if sender is not None:
        app.state.email_sender = sender
    return app, engine


def test_valid_signup_and_session(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        created = client.post("/auth/signup", json=SIGNUP)
        assert created.status_code == 201
        body = created.json()["user"]
        assert body["email"] == "ada@payintel.test"
        assert body["role"] == "user"
        assert "password" not in body
        assert "password_hash" not in body
        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "ada@payintel.test"
        factory = session_factory(engine)
        with factory() as session:
            events = list(
                session.scalars(select(AuditEvent).where(AuditEvent.event_type == "SIGNUP"))
            )
            assert events
            assert "password" not in str(events[0].payload_json).lower()


def test_duplicate_email_rejected(tmp_path) -> None:
    app, _engine = _app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/auth/signup", json=SIGNUP).status_code == 201
        again = client.post("/auth/signup", json=SIGNUP)
        assert again.status_code == 409


def test_invalid_email_and_weak_and_mismatch(tmp_path) -> None:
    app, _engine = _app(tmp_path)
    with TestClient(app) as client:
        invalid = client.post(
            "/auth/signup",
            json={**SIGNUP, "email": "not-an-email"},
        )
        weak = client.post(
            "/auth/signup",
            json={
                **SIGNUP,
                "email": "weak@payintel.test",
                "password": "short",
                "confirm_password": "short",
            },
        )
        mismatch = client.post(
            "/auth/signup",
            json={**SIGNUP, "email": "mismatch@payintel.test", "confirm_password": "Otheruser1!x"},
        )
        assert invalid.status_code == 422
        assert weak.status_code == 422
        assert mismatch.status_code == 422


def test_signup_cannot_self_promote(tmp_path) -> None:
    app, _engine = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/auth/signup", json={**SIGNUP, "role": "admin"})
        assert response.status_code == 422


def test_valid_login_wrong_password_and_unknown_user(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        authenticate_client(client, engine)
        client.post("/auth/logout")
        ok = login(client)
        assert ok.status_code == 200
        client.post("/auth/logout")
        wrong = login(client, password="Wronguser1!x")
        missing = login(client, email="missing@payintel.test")
        assert wrong.status_code == 401
        assert missing.status_code == 401
        assert wrong.json()["detail"] == missing.json()["detail"]


def test_suspended_user_cannot_login(tmp_path) -> None:
    app, engine = _app(tmp_path)
    factory = session_factory(engine)
    with factory() as session:
        insert_user(session, status="suspended")
    with TestClient(app) as client:
        response = login(client)
        assert response.status_code == 403


def test_user_cannot_access_admin_admin_can(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        authenticate_client(client, engine)
        denied = client.get("/admin/overview")
        assert denied.status_code == 403
    with TestClient(app) as admin_client:
        authenticate_client(
            admin_client,
            engine,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role="admin",
            name="Admin",
        )
        allowed = admin_client.get("/admin/overview")
        assert allowed.status_code == 200
        assert "total_users" in allowed.json()


def test_unauthenticated_protected_route(tmp_path) -> None:
    app, _engine = _app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/investigations")
        assert response.status_code == 401


def test_role_change_requires_admin_and_is_audited(tmp_path) -> None:
    app, engine = _app(tmp_path)
    factory = session_factory(engine)
    with factory() as session:
        target = insert_user(session, email="target@payintel.test", name="Target")
    with TestClient(app) as user_client:
        authenticate_client(user_client, engine)
        forbidden = user_client.post(f"/admin/users/{target.user_id}/role", json={"role": "admin"})
        assert forbidden.status_code == 403
    with TestClient(app) as admin_client:
        authenticate_client(
            admin_client,
            engine,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role="admin",
            name="Admin",
        )
        changed = admin_client.post(f"/admin/users/{target.user_id}/role", json={"role": "admin"})
        assert changed.status_code == 200
        assert changed.json()["role"] == "admin"
    with factory() as session:
        events = list(
            session.scalars(select(AuditEvent).where(AuditEvent.event_type == "ROLE_CHANGED"))
        )
        assert events
        payload = events[0].payload_json
        assert payload["from_role"] == "user"
        assert payload["to_role"] == "admin"
        assert "password" not in payload


def test_last_admin_cannot_be_demoted(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        created = authenticate_client(
            client,
            engine,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role="admin",
            name="Admin",
        )
        admin_id = created.json()["user"]["user_id"]
        response = client.post(f"/admin/users/{admin_id}/role", json={"role": "user"})
        assert response.status_code == 400


def test_logout_and_expired_session(tmp_path) -> None:
    app, engine = _app(tmp_path)
    with TestClient(app) as client:
        authenticate_client(client, engine)
        assert client.get("/auth/me").status_code == 200
        assert client.post("/auth/logout").status_code == 200
        assert client.get("/auth/me").status_code == 401
    factory = session_factory(engine)
    with factory() as session:
        user = insert_user(session, email="expired@payintel.test")
        row = AuthSession(
            session_id="expiredsession1",
            user_id=user.user_id,
            token_hash=hash_token("expired-token-value"),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
        )
        session.add(row)
        session.commit()
    with TestClient(app) as client:
        client.cookies.set("payintel_session", "expired-token-value")
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


def test_forgot_password_is_generic_and_reset_works(tmp_path) -> None:
    sender = CapturingEmailSender()
    app, engine = _app(tmp_path, sender=sender)
    factory = session_factory(engine)
    with factory() as session:
        insert_user(session)
    with TestClient(app) as client:
        missing = client.post("/auth/forgot-password", json={"email": "nobody@payintel.test"})
        existing = client.post("/auth/forgot-password", json={"email": TEST_EMAIL})
        assert missing.status_code == 200
        assert existing.status_code == 200
        assert missing.json()["message"] == existing.json()["message"]
        assert sender.messages
        token = sender.messages[0].body.rsplit("token=", 1)[-1].split()[0]
        assert token not in existing.text
        reset = client.post(
            "/auth/reset-password",
            json={"token": token, "password": "Newuser1!x", "confirm_password": "Newuser1!x"},
        )
        assert reset.status_code == 200
        assert login(client, password="Newuser1!x").status_code == 200
    with factory() as session:
        events = [row.event_type for row in session.scalars(select(AuditEvent))]
        assert "PASSWORD_RESET_REQUEST" in events
        assert "PASSWORD_RESET" in events
        for row in session.scalars(select(AuditEvent)):
            blob = str(row.payload_json).lower()
            assert "password" not in blob
            assert "token" not in blob
