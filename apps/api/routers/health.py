from fastapi import APIRouter, Depends, HTTPException, status
from payops_core.config import Settings
from payops_core.models import HealthResponse, ReadyResponse

from apps.api.boot import ping_database
from apps.api.deps import get_app_settings

router = APIRouter(tags=["health"])

_VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness",
    description="Process health. Does not query payments data.",
)
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment, version=_VERSION)


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    summary="Readiness",
    description="Confirms the process can reach the configured database.",
    responses={503: {"description": "Database unreachable"}},
)
def ready(settings: Settings = Depends(get_app_settings)) -> ReadyResponse:
    try:
        ping_database()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return ReadyResponse(
        status="ok",
        environment=settings.environment,
        version=_VERSION,
        database="up",
    )
