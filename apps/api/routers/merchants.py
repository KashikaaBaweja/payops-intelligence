from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from payops_core.data.models import Merchant
from payops_core.models.api import ErrorResponse, MerchantMetricsResponse
from payops_core.models.schemas import AnalyticsOperation, AnalyticsRequest, MerchantHealthScore
from payops_core.tools.merchant_health import score_merchant
from payops_core.tools.sql_gateway import ALLOWED_OPERATIONS, SqlToolGateway
from sqlalchemy.orm import Session

from apps.api.deps import get_session, get_store
from apps.api.query import parse_window, require_id
from apps.api.store import InvestigationStore

router = APIRouter(tags=["merchants"])

_DEFAULT_OPERATIONS: tuple[AnalyticsOperation, ...] = (
    "get_success_rate",
    "get_failure_rate",
    "get_refund_rate",
    "get_dispute_rate",
    "get_webhook_failure_rate",
)
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid merchant or window"},
    404: {"model": ErrorResponse, "description": "Merchant not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.get(
    "/merchants/{id}/health",
    response_model=MerchantHealthScore,
    responses=_ERROR_RESPONSES,
    summary="Explainable merchant health score",
    description="Deterministic weighted score. No machine-learning model is used.",
)
def merchant_health(
    id: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
    store: InvestigationStore = Depends(get_store),
) -> MerchantHealthScore:
    merchant_id = require_id(id, "id")
    _require_merchant(session, merchant_id)
    window = parse_window(start, end)
    try:
        result = score_merchant(session, merchant_id, window)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    store.index_evidence([result.to_evidence()])
    return result


@router.get(
    "/merchants/{id}/metrics",
    response_model=MerchantMetricsResponse,
    responses=_ERROR_RESPONSES,
    summary="Merchant payment metrics",
    description="Catalog analytics only. Raw SQL is rejected.",
)
def merchant_metrics(
    id: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    operation: Annotated[list[str] | None, Query()] = None,
    session: Session = Depends(get_session),
    store: InvestigationStore = Depends(get_store),
) -> MerchantMetricsResponse:
    merchant_id = require_id(id, "id")
    _require_merchant(session, merchant_id)
    window = parse_window(start, end)
    requested = operation or list(_DEFAULT_OPERATIONS)
    selected: list[AnalyticsOperation] = []
    for name in requested:
        if name not in ALLOWED_OPERATIONS:
            raise HTTPException(status_code=400, detail=f"unknown operation: {name}")
        selected.append(cast(AnalyticsOperation, name))
    gateway = SqlToolGateway(session)
    metrics = [
        gateway.run(AnalyticsRequest(operation=name, window=window, merchant_id=merchant_id))
        for name in selected
    ]
    store.index_evidence([item.to_evidence() for item in metrics])
    return MerchantMetricsResponse(merchant_id=merchant_id, window=window, metrics=metrics)


def _require_merchant(session: Session, merchant_id: str) -> None:
    if session.get(Merchant, merchant_id) is None:
        raise HTTPException(status_code=404, detail="merchant not found")
