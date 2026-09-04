from fastapi import APIRouter, Depends
from payops_core.config import Settings
from payops_core.models import HealthResponse

from apps.api.deps import get_app_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness",
    description="Process health. Does not query payments data.",
)
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment, version="0.1.0")
