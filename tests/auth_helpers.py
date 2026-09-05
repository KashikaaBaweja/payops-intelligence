from payops_core.data.engine import session_factory
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.auth_service import create_user

TEST_PASSWORD = "Testuser1!x"
TEST_EMAIL = "operator@payintel.test"
ADMIN_EMAIL = "admin@payintel.test"
ADMIN_PASSWORD = "Adminuser1!x"


def insert_user(
    session: Session,
    *,
    email: str = TEST_EMAIL,
    password: str = TEST_PASSWORD,
    role: str = "user",
    name: str = "Test Operator",
    status: str = "active",
):
    user = create_user(session, name=name, email=email, password=password, role=role)
    user.status = status
    session.commit()
    return user


def login(client, email: str = TEST_EMAIL, password: str = TEST_PASSWORD):
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response


def authenticate_client(client, engine: Engine, **kwargs):
    factory = session_factory(engine)
    with factory() as session:
        insert_user(session, **kwargs)
    response = login(
        client,
        email=kwargs.get("email", TEST_EMAIL),
        password=kwargs.get("password", TEST_PASSWORD),
    )
    assert response.status_code == 200, response.text
    return response


def authenticate_session_client(client, session: Session, **kwargs):
    insert_user(session, **kwargs)
    response = login(
        client,
        email=kwargs.get("email", TEST_EMAIL),
        password=kwargs.get("password", TEST_PASSWORD),
    )
    assert response.status_code == 200, response.text
    return response
