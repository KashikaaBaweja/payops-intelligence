from collections.abc import Iterator
from logging import getLogger
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from payops_core.auth.audit import EVENT_ADMIN_ACCESS, record_audit
from payops_core.auth.emailer import EmailSender, build_email_sender
from payops_core.config import Settings, get_settings
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import AuthUser
from payops_core.rag.errors import IngestError
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever, build_retriever
from payops_core.rag.vector_store import InMemoryVectorStore
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.auth_service import resolve_session
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


def get_store(session: Session = Depends(get_session)) -> InvestigationStore:
    return InvestigationStore(session)


def get_email_sender(request: Request) -> EmailSender:
    existing = getattr(request.app.state, "email_sender", None)
    if existing is not None:
        return existing
    sender = build_email_sender(get_settings())
    request.app.state.email_sender = sender
    return sender


def _session_token(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.cookie_name)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthUser:
    user, reason = resolve_session(session, _session_token(request, settings))
    if user is None:
        if reason == "expired":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session expired. Sign in again.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required.",
        )
    return user


def require_admin(
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    # Write the audit row on a sidecar session so GET handlers persist
    # ADMIN_ACCESS without committing (and expiring) in-flight request work.
    factory = session_factory(get_engine(request))
    with factory() as isolated:
        record_audit(
            isolated,
            EVENT_ADMIN_ACCESS,
            actor_id=user.user_id,
            resource_id=user.user_id,
            metadata={"path": request.url.path},
            commit=True,
        )
    return user


def get_retriever(request: Request) -> DocumentRetriever:
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        retriever = build_startup_retriever()
        request.app.state.retriever = retriever
    return retriever


def build_startup_retriever() -> DocumentRetriever:
    settings = get_settings()
    if settings.vector_backend == "pgvector":
        retriever = build_retriever()
        try:
            if retriever.store.count() > 0:
                return retriever
            store, count = ingest_corpus(
                directory=Path(settings.corpus_dir),
                store=retriever.store,
            )
            logger.info("corpus_ingested backend=pgvector chunks=%s", count)
            return DocumentRetriever(store)
        except IngestError:
            logger.warning("corpus_unavailable backend=pgvector")
            return retriever
    try:
        store, _count = ingest_corpus(
            directory=Path(settings.corpus_dir),
            store=InMemoryVectorStore(),
        )
    except IngestError:
        logger.warning("corpus_unavailable backend=memory")
        return DocumentRetriever(InMemoryVectorStore())
    return DocumentRetriever(store)
