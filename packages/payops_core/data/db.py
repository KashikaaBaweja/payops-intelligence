from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from payops_core.config import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def make_engine(url: str | None = None) -> Engine:
    database_url = url or get_settings().database_url
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def apply_schema(engine: Engine) -> None:
    statements = SCHEMA_PATH.read_text().split(";")
    with engine.begin() as conn:
        for statement in statements:
            sql = statement.strip()
            if sql:
                conn.execute(text(sql))
