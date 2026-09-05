from __future__ import annotations

import uuid
from datetime import datetime, timezone
from logging import getLogger
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from payops_core.auth.audit import EVENT_RESEARCH_COMPLETED, EVENT_RESEARCH_STARTED, record_audit
from payops_core.data.models import AuthUser, Merchant
from payops_core.graph.build import report_from, run_investigation
from payops_core.graph.state import InvestigationState
from payops_core.models.api import (
    ErrorResponse,
    InvestigationCreateRequest,
    InvestigationDeleteResponse,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationSummary,
    InvestigationTraceResponse,
)
from payops_core.models.schemas import EvidenceBundle
from payops_core.query_language import detect_query_language, retrieval_query
from payops_core.rag.retriever import DocumentRetriever
from sqlalchemy.orm import Session

from apps.api.deps import get_current_user, get_retriever, get_session, get_store
from apps.api.query import require_id
from apps.api.store import InvestigationStore, StoredInvestigation

logger = getLogger(__name__)

router = APIRouter(tags=["investigations"], dependencies=[Depends(get_current_user)])


def _status_from_state(state: InvestigationState | dict[str, Any]) -> tuple[str, str | None]:
    if state.get("timed_out"):
        return "failed", str(state.get("error") or "Investigation timed out")[:300]
    if state.get("error"):
        return "failed", str(state.get("error"))[:300]
    return "completed", None


def _persistable_error(exc: Exception, graph_error: Any = None) -> str:
    if graph_error:
        return str(graph_error)[:300]
    return f"{type(exc).__name__}: {exc}"[:300]


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((perf_counter() - started) * 1000)))


def _query_language(record: StoredInvestigation) -> str:
    return detect_query_language(record.question)


def _response_language(record: StoredInvestigation) -> str:
    report = record.report
    if report is not None and getattr(report, "response_language", None):
        return report.response_language
    return _query_language(record)


def _retrieval_query(record: StoredInvestigation) -> str | None:
    report = record.report
    if report is not None and getattr(report, "retrieval_query", None):
        return report.retrieval_query
    return retrieval_query(record.question)


def _summary(record: StoredInvestigation) -> InvestigationSummary:
    return InvestigationSummary(
        investigation_id=record.investigation_id,
        question=record.question,
        status=record.status,  # type: ignore[arg-type]
        created_at=record.created_at,
        merchant_id=record.report.merchant_id if record.report else None,
        confidence=record.report.confidence if record.report else None,
        evidence_sufficient=record.report.evidence_sufficient if record.report else None,
        input_method=record.input_method,  # type: ignore[arg-type]
        duration_ms=record.duration_ms,
        query_language=_query_language(record),  # type: ignore[arg-type]
    )


def _response(record: StoredInvestigation) -> InvestigationResponse:
    return InvestigationResponse(
        investigation_id=record.investigation_id,
        status=record.status,  # type: ignore[arg-type]
        question=record.question,
        original_query=record.question,
        input_method=record.input_method,  # type: ignore[arg-type]
        query_language=_query_language(record),  # type: ignore[arg-type]
        response_language=_response_language(record),  # type: ignore[arg-type]
        retrieval_query=_retrieval_query(record),
        created_at=record.created_at,
        report=record.report,
        error=record.error,
        duration_ms=record.duration_ms,
    )


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
    return InvestigationListResponse(
        items=[_summary(record) for record in records],
        total=store.count_runs(),
    )


@router.delete(
    "/investigations",
    response_model=InvestigationDeleteResponse,
    summary="Clear query history",
    description=(
        "Deletes persisted investigation transcripts, traces, and cited evidence. "
        "Microphone audio is never stored."
    ),
)
def delete_all_investigations(
    store: InvestigationStore = Depends(get_store),
) -> InvestigationDeleteResponse:
    return InvestigationDeleteResponse(deleted=store.delete_all())


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
    user: AuthUser = Depends(get_current_user),
) -> InvestigationResponse:
    if payload.merchant_id:
        require_id(payload.merchant_id, "merchant_id")
        if session.get(Merchant, payload.merchant_id) is None:
            raise HTTPException(status_code=404, detail="merchant not found")
    investigation_id = uuid.uuid4().hex
    opened_at = datetime.now(timezone.utc)
    started = perf_counter()
    query = payload.query or payload.question or ""
    record_audit(
        session,
        EVENT_RESEARCH_STARTED,
        actor_id=user.user_id,
        resource_id=investigation_id,
        metadata={"input_method": payload.input_method},
    )
    session.commit()
    state: InvestigationState | dict[str, Any] | None = None
    try:
        state = run_investigation(
            query,
            retriever=retriever,
            session=session,
            max_iterations=payload.max_iterations,
            merchant_id=payload.merchant_id,
            input_method=payload.input_method,
            language=payload.language,
        )
        report = report_from(state)
    except Exception as exc:
        logger.exception("investigation_failed", extra={"investigation_id": investigation_id})
        failed: dict[str, Any] = dict(state or {})
        store.put(
            StoredInvestigation(
                investigation_id=investigation_id,
                question=query,
                input_method=payload.input_method,
                status="failed",
                report=failed.get("report"),
                trace=list(failed.get("trace") or []),
                evidence=list((failed.get("evidence") or EvidenceBundle()).items),
                error=_persistable_error(exc, failed.get("error")),
                created_at=opened_at,
                duration_ms=_elapsed_ms(started),
            )
        )
        raise HTTPException(status_code=500, detail="Investigation failed") from None
    run_status, error = _status_from_state(state)
    evidence = list((state.get("evidence") or EvidenceBundle()).items)  # type: ignore[union-attr]
    duration_ms = _elapsed_ms(started)
    record = StoredInvestigation(
        investigation_id=investigation_id,
        question=query,
        input_method=payload.input_method,
        status=run_status,
        report=report,
        trace=list(state.get("trace") or []),
        evidence=evidence,
        error=error,
        created_at=opened_at,
        duration_ms=duration_ms,
    )
    store.put(record)
    record_audit(
        session,
        EVENT_RESEARCH_COMPLETED,
        actor_id=user.user_id,
        resource_id=investigation_id,
        metadata={"status": run_status},
        commit=True,
    )
    logger.info(
        "investigation_completed",
        extra={
            "investigation_id": investigation_id,
            "status": run_status,
            "input_method": payload.input_method,
            "duration_ms": duration_ms,
        },
    )
    response.headers["Location"] = f"/investigations/{investigation_id}"
    return _response(record)


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
    return _response(record)


@router.delete(
    "/investigations/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERROR_RESPONSES,
    summary="Delete one query from history",
    description="Removes that investigation transcript and trace. Audio is never stored.",
)
def delete_investigation(
    id: str,
    store: InvestigationStore = Depends(get_store),
) -> Response:
    require_id(id, "id")
    if not store.delete(id):
        raise HTTPException(status_code=404, detail="investigation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
