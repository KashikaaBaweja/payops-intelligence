import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGES = _ROOT / "packages"
for _path in (str(_PACKAGES), str(_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from payops_core.config import get_settings
from payops_core.logging import configure_logging
from payops_core.models.api import ErrorResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.deps import build_startup_retriever
from apps.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from apps.api.middleware import RequestIdMiddleware
from apps.api.routers.evidence import router as evidence_router
from apps.api.routers.health import router as health_router
from apps.api.routers.investigations import router as investigations_router
from apps.api.routers.merchants import router as merchants_router
from apps.api.store import InvestigationStore

logger = getLogger(__name__)

_TAGS = [
    {"name": "health", "description": "Process liveness"},
    {"name": "investigations", "description": "Run and inspect investigations"},
    {"name": "merchants", "description": "Health scores and catalog metrics"},
    {"name": "evidence", "description": "Resolve cited evidence items"},
]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.json_logs)
    if getattr(application.state, "investigations", None) is None:
        application.state.investigations = InvestigationStore()
    if getattr(application.state, "retriever", None) is None:
        application.state.retriever = build_startup_retriever()
    logger.info("api_starting environment=%s", settings.environment)
    yield
    logger.info("api_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="PayOps Intelligence API",
        version="0.1.0",
        description=(
            "Production-style API for payment investigations, merchant health, "
            "and evidence lookup. Local demo mode does not require API keys."
        ),
        lifespan=lifespan,
        openapi_tags=_TAGS,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(health_router)
    application.include_router(investigations_router)
    application.include_router(merchants_router)
    application.include_router(evidence_router)
    return application


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
