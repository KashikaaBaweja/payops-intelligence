from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from payops_core.config import get_settings
from payops_core.data.base import Base


def make_engine(url: str | None = None) -> Engine:
    database_url = url or get_settings().database_url
    connect_args: dict = {}
    engine_kwargs: dict = {"future": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            engine_kwargs["poolclass"] = StaticPool
        elif database_url.startswith("sqlite:///") and ":memory:" not in database_url:
            db_path = Path(database_url.replace("sqlite:///", "", 1))
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
    if connect_args:
        engine_kwargs["connect_args"] = connect_args
    return create_engine(database_url, **engine_kwargs)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
