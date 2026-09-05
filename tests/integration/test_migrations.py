from alembic.config import Config
from payops_core.config import get_settings
from payops_core.data.engine import make_engine
from sqlalchemy import inspect

from alembic import command


def test_alembic_upgrade_creates_payment_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("PAYOPS_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    inspector = inspect(make_engine(str(get_settings().database_url)))
    tables = set(inspector.get_table_names())
    assert {
        "merchants",
        "orders",
        "payments",
        "refunds",
        "settlements",
        "disputes",
        "webhook_events",
        "payment_methods",
        "error_codes",
        "document_chunks",
        "investigation_runs",
        "evidence_index",
        "ledger_accounts",
        "ledger_transfers",
        "ledger_entries",
        "ledger_audit_events",
        "auth_users",
        "auth_sessions",
        "password_reset_tokens",
        "audit_events",
    }.issubset(tables)
    get_settings.cache_clear()
