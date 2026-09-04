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
from fastapi.middleware.cors import CORSMiddleware
from payops_core.config import get_settings
from payops_core.logging import configure_logging

from apps.api.routers.health import router as health_router

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("api_starting environment=%s", settings.environment)
    yield
    logger.info("api_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="PayOps Intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
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
