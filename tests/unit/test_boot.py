from payops_core.config import get_settings
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import Merchant
from sqlalchemy import func, select

from apps.api.boot import migrate, ping_database, seed_if_empty, wait_for_database


def test_wait_and_ping_sqlite(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "boot.db"
    monkeypatch.setenv("PAYOPS_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        wait_for_database(timeout_seconds=5)
        ping_database()
    finally:
        get_settings.cache_clear()


def test_migrate_then_seed_if_empty(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("PAYOPS_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        migrate()
        seed_if_empty()
        engine = make_engine()
        factory = session_factory(engine)
        with factory() as session:
            first = session.scalar(select(func.count()).select_from(Merchant))
        seed_if_empty()
        with factory() as session:
            second = session.scalar(select(func.count()).select_from(Merchant))
        assert first == 5
        assert second == 5
    finally:
        get_settings.cache_clear()


def test_wait_for_database_times_out(monkeypatch) -> None:
    monkeypatch.setenv(
        "PAYOPS_DATABASE_URL",
        "postgresql+psycopg://payops:payops@127.0.0.1:9/missing",
    )
    get_settings.cache_clear()
    try:
        try:
            wait_for_database(timeout_seconds=1)
            raised = False
        except RuntimeError as exc:
            raised = True
            assert "database not ready" in str(exc)
        assert raised
    finally:
        get_settings.cache_clear()
