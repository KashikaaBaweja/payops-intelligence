"""Container/process boot: wait for the database, migrate, and seed if empty."""

from __future__ import annotations

import time
from logging import getLogger
from pathlib import Path

from alembic.config import Config
from payops_core.config import get_settings
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import Merchant
from payops_core.data.seed import seed
from sqlalchemy import func, select, text

from alembic import command

logger = getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return cfg


def wait_for_database(timeout_seconds: float | None = None) -> None:
    settings = get_settings()
    timeout = settings.db_wait_seconds if timeout_seconds is None else timeout_seconds
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            engine = make_engine()
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"database not ready after {timeout:.0f}s: {last}") from last


def ping_database() -> None:
    engine = make_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def migrate() -> None:
    command.upgrade(alembic_config(), "head")


def seed_if_empty() -> None:
    engine = make_engine()
    factory = session_factory(engine)
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(Merchant)) or 0
    if count:
        logger.info("seed_skipped merchants=%s", count)
        return
    stats = seed()
    logger.info("seed_completed payments=%s", stats["payments"])


def main() -> None:
    from payops_core.logging import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.json_logs)
    wait_for_database()
    if settings.auto_migrate:
        migrate()
    if settings.seed_on_start:
        seed_if_empty()


if __name__ == "__main__":
    main()
