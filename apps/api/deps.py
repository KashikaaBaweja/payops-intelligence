from collections.abc import Iterator
from logging import getLogger
from pathlib import Path

from fastapi import Request
from payops_core.config import Settings, get_settings
from payops_core.data.engine import make_engine, session_factory
from payops_core.rag.errors import IngestError
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever, build_retriever
from payops_core.rag.vector_store import InMemoryVectorStore
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.store import InvestigationStore

logger = getLogger(__name__)


def get_app_settings() -> Settings:
    return get_settings()


def get_engine(request: Request) -> Engine:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        engine = make_engine()
        request.app.state.engine = engine
    return engine


def get_session(request: Request) -> Iterator[Session]:
    session = session_factory(get_engine(request))()
    try:
        yield session
    finally:
        session.close()


def get_store(request: Request) -> InvestigationStore:
    store = getattr(request.app.state, "investigations", None)
    if store is None:
        store = InvestigationStore()
        request.app.state.investigations = store
    return store


def get_retriever(request: Request) -> DocumentRetriever:
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        retriever = build_startup_retriever()
        request.app.state.retriever = retriever
    return retriever


def build_startup_retriever() -> DocumentRetriever:
    settings = get_settings()
    if settings.vector_backend == "pgvector":
        return build_retriever()
    try:
        store, _count = ingest_corpus(
            directory=Path(settings.corpus_dir),
            store=InMemoryVectorStore(),
        )
    except IngestError:
        logger.warning("corpus_unavailable backend=memory")
        return DocumentRetriever(InMemoryVectorStore())
    return DocumentRetriever(store)
