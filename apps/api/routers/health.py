from fastapi import APIRouter, Depends, HTTPException, status
from payops_core.config import Settings
from payops_core.models import HealthResponse, ReadyResponse
from payops_core.models.api import ServiceStatus, SystemHealthResponse

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


@router.get(
    "/health/services",
    response_model=SystemHealthResponse,
    summary="Live service statuses",
    description="Live process, database, retrieval backend, and ML status. Demo has no LLM.",
)
def services(settings: Settings = Depends(get_app_settings)) -> SystemHealthResponse:
    items: list[ServiceStatus] = [
        ServiceStatus(name="api", status="ok", detail=f"PayIntel API {_VERSION}"),
    ]
    try:
        ping_database()
        items.append(
            ServiceStatus(
                name="database", status="ok", detail=settings.database_url.split("://")[0]
            )
        )
    except Exception:
        items.append(ServiceStatus(name="database", status="down", detail="unreachable"))
    items.append(
        ServiceStatus(
            name="vector_db",
            status="ok" if settings.vector_backend else "disabled",
            detail=f"{settings.vector_backend} hashing retriever",
        )
    )
    items.append(
        ServiceStatus(
            name="llm",
            status="disabled" if settings.llm_provider == "demo" else "ok",
            detail=(
                "Demo mode: no LLM client. Graph is deterministic."
                if settings.llm_provider == "demo"
                else f"provider={settings.llm_provider}"
            ),
        )
    )
    items.append(
        ServiceStatus(name="agents", status="ok", detail="LangGraph process-local orchestrator")
    )
    try:
        import sklearn  # noqa: F401

        items.append(
            ServiceStatus(name="ml", status="ok", detail="sklearn classifier and regressor")
        )
    except Exception as exc:
        items.append(ServiceStatus(name="ml", status="down", detail=str(exc)[:160]))
    database = next((item for item in items if item.name == "database"), None)
    worst = {item.status for item in items}
    overall: str = "ok"
    if database is not None and database.status == "down":
        overall = "down"
    elif "down" in worst or "degraded" in worst:
        overall = "degraded"
    return SystemHealthResponse(
        status=overall,  # type: ignore[arg-type]
        environment=settings.environment,
        version=_VERSION,
        services=items,
    )
