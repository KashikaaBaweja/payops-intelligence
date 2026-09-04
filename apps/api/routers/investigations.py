from __future__ import annotations

import uuid
from logging import getLogger
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Response, status
from payops_core.data.models import Merchant
from payops_core.graph.build import report_from, run_investigation
from payops_core.models.api import (
    ErrorResponse,
    InvestigationCreateRequest,
    InvestigationResponse,
    InvestigationTraceResponse,
)
from payops_core.models.schemas import EvidenceBundle
from payops_core.rag.retriever import DocumentRetriever
from sqlalchemy.orm import Session

from apps.api.deps import get_retriever, get_session, get_store
from apps.api.query import require_id
from apps.api.store import InvestigationStore, StoredInvestigation

logger = getLogger(__name__)

router = APIRouter(tags=["investigations"])

_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Investigation not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Investigation failed"},
}


@router.post(
    "/investigations",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
    summary="Run an investigation",
    description=(
        "Plan, retrieve, and write a structured incident report. "
        "Does not require an LLM API key in demo mode."
    ),
)
def create_investigation(
    payload: InvestigationCreateRequest,
    response: Response,
    session: Session = Depends(get_session),
    retriever: DocumentRetriever = Depends(get_retriever),
    store: InvestigationStore = Depends(get_store),
) -> InvestigationResponse:
    if payload.merchant_id:
        require_id(payload.merchant_id, "merchant_id")
        if session.get(Merchant, payload.merchant_id) is None:
            raise HTTPException(status_code=404, detail="merchant not found")
    investigation_id = uuid.uuid4().hex
    started = perf_counter()
    try:
        state = run_investigation(
            payload.question,
            retriever=retriever,
            session=session,
            max_iterations=payload.max_iterations,
        )
        report = report_from(state)
    except Exception:
        logger.exception("investigation_failed", extra={"investigation_id": investigation_id})
        record = StoredInvestigation(
            investigation_id=investigation_id,
            question=payload.question,
            status="failed",
            report=None,
            trace=[],
            evidence=[],
            error="Investigation failed",
        )
        store.put(record)
        raise HTTPException(status_code=500, detail="Investigation failed") from None
    evidence = list((state.get("evidence") or EvidenceBundle()).items)
    record = StoredInvestigation(
        investigation_id=investigation_id,
        question=payload.question,
        status="completed",
        report=report,
        trace=list(state.get("trace") or []),
        evidence=evidence,
    )
    store.put(record)
    logger.info(
        "investigation_completed",
        extra={
            "investigation_id": investigation_id,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    response.headers["Location"] = f"/investigations/{investigation_id}"
    return InvestigationResponse(
        investigation_id=investigation_id,
        status="completed",
        question=payload.question,
        created_at=record.created_at,
        report=report,
    )


@router.get(
    "/investigations/{id}",
    response_model=InvestigationResponse,
    responses=_ERROR_RESPONSES,
    summary="Get an investigation report",
)
def get_investigation(
    id: str,
    store: InvestigationStore = Depends(get_store),
) -> InvestigationResponse:
    require_id(id, "id")
    record = store.get(id)
    if record is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return InvestigationResponse(
        investigation_id=record.investigation_id,
        status=record.status,  # type: ignore[arg-type]
        question=record.question,
        created_at=record.created_at,
        report=record.report,
        error=record.error,
    )


@router.get(
    "/investigations/{id}/trace",
    response_model=InvestigationTraceResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the investigation execution trace",
    description="Structured node/tool events only. No private chain-of-thought.",
)
def get_investigation_trace(
    id: str,
    store: InvestigationStore = Depends(get_store),
) -> InvestigationTraceResponse:
    require_id(id, "id")
    record = store.get(id)
    if record is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return InvestigationTraceResponse(
        investigation_id=record.investigation_id,
        events=record.trace,
    )
