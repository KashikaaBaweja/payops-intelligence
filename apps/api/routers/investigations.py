from __future__ import annotations

import uuid
from logging import getLogger
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from payops_core.data.models import Merchant
from payops_core.graph.build import report_from, run_investigation
from payops_core.models.api import (
    ErrorResponse,
    InvestigationCreateRequest,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationSummary,
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


def _status_from_state(state: dict[str, Any]) -> tuple[str, str | None]:
    if state.get("timed_out"):
        return "failed", str(state.get("error") or "Investigation timed out")[:300]
    if state.get("error"):
        return "failed", str(state.get("error"))[:300]
    return "completed", None


def _persistable_error(exc: Exception, graph_error: Any = None) -> str:
    if graph_error:
        return str(graph_error)[:300]
    return f"{type(exc).__name__}: {exc}"[:300]

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Investigation not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Investigation failed"},
}


@router.get(
    "/investigations",
    response_model=InvestigationListResponse,
    summary="List recent investigations",
)
def list_investigations(
    store: InvestigationStore = Depends(get_store),
) -> InvestigationListResponse:
    records = store.list_recent(20)
    items = [
        InvestigationSummary(
            investigation_id=record.investigation_id,
            question=record.question,
            status=record.status,  # type: ignore[arg-type]
            created_at=record.created_at,
            merchant_id=record.report.merchant_id if record.report else None,
            confidence=record.report.confidence if record.report else None,
            evidence_sufficient=record.report.evidence_sufficient if record.report else None,
        )
        for record in records
    ]
    return InvestigationListResponse(items=items, total=store.count_runs())


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
    state: dict[str, Any] | None = None
    try:
        state = run_investigation(
            payload.question,
            retriever=retriever,
            session=session,
            max_iterations=payload.max_iterations,
            merchant_id=payload.merchant_id,
        )
        report = report_from(state)
    except Exception as exc:
        logger.exception("investigation_failed", extra={"investigation_id": investigation_id})
        failed = state or {}
        record = StoredInvestigation(
            investigation_id=investigation_id,
            question=payload.question,
            status="failed",
            report=failed.get("report"),
            trace=list(failed.get("trace") or []),
            evidence=list((failed.get("evidence") or EvidenceBundle()).items),
            error=_persistable_error(exc, failed.get("error")),
        )
        store.put(record)
        raise HTTPException(status_code=500, detail="Investigation failed") from None
    status, error = _status_from_state(state)
    evidence = list((state.get("evidence") or EvidenceBundle()).items)
    record = StoredInvestigation(
        investigation_id=investigation_id,
        question=payload.question,
        status=status,
        report=report,
        trace=list(state.get("trace") or []),
        evidence=evidence,
        error=error,
    )
    store.put(record)
    logger.info(
        "investigation_completed",
        extra={
            "investigation_id": investigation_id,
            "status": status,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    response.headers["Location"] = f"/investigations/{investigation_id}"
    return InvestigationResponse(
        investigation_id=investigation_id,
        status=status,  # type: ignore[arg-type]
        question=payload.question,
        created_at=record.created_at,
        report=report,
        error=error,
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
