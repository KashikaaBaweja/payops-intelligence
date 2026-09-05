from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from payops_core.agents.planner import DEFAULT_WINDOW
from payops_core.auth.audit import (
    EVENT_ROLE_CHANGED,
    EVENT_USER_ACTIVATED,
    EVENT_USER_SUSPENDED,
    record_audit,
)
from payops_core.config import Settings
from payops_core.data.models import AuditEvent, AuthUser, InvestigationRun, LedgerTransfer, Payment
from payops_core.ledger.transfer import get_transfer, list_recent_transfers
from payops_core.ml.errors import InsufficientTrainingData
from payops_core.models.auth import (
    AdminAgentRow,
    AdminMlModelRow,
    AdminOverviewResponse,
    AdminTransactionDetail,
    AdminTransactionRow,
    AdminUserListResponse,
    AdminUserRow,
    AuditEventRow,
    AuditListResponse,
    PublicUser,
    RoleChangeRequest,
)
from payops_core.tools.ml_risk import score_latency, score_risk
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.auth_service import count_active_admins, get_user, revoke_user_sessions
from apps.api.boot import ping_database
from apps.api.deps import get_app_settings, get_engine, get_session, get_store, require_admin
from apps.api.query import require_id
from apps.api.store import InvestigationStore

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_AGENT_LABELS = (
    ("planner", "Orchestrator"),
    ("researcher", "Researcher"),
    ("rag", "RAG"),
    ("analyst", "Data Analyst"),
    ("risk", "ML Agent"),
    ("integrity", "Transaction Agent"),
    ("critic", "Critic"),
    ("writer", "Report Writer"),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _public(user: AuthUser) -> AdminUserRow:
    return AdminUserRow(
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        last_login_at=user.last_login_at,
    )


def _stage_for_event(event: dict[str, Any]) -> str | None:
    node = event.get("node")
    action = str(event.get("action") or "")
    tool = event.get("tool")
    decision = event.get("decision")
    if node == "planner":
        return "planner"
    if node == "investigate":
        if action.startswith("rag_"):
            return "rag"
        if tool == "search_docs" or decision == "retrieve_docs":
            return "researcher"
        if tool in {"ml_risk", "ml_regression"} or decision in {"score_risk", "score_regression"}:
            return "risk"
        if tool == "validate_integrity" or decision == "validate_integrity":
            return "integrity"
        return "analyst"
    if node in {"aggregate", "sufficiency", "refine"}:
        return "rag"
    if node == "incident_risk":
        return "analyst"
    if node in {"verifier", "critic"}:
        return "critic"
    if node == "writer":
        return "writer"
    return None


@router.get("/overview", response_model=AdminOverviewResponse)
def overview(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    store: InvestigationStore = Depends(get_store),
) -> AdminOverviewResponse:
    now = _utcnow()
    active_since = now - timedelta(hours=24)
    total_users = session.scalar(select(func.count()).select_from(AuthUser))
    active_users = session.scalar(
        select(func.count()).select_from(AuthUser).where(AuthUser.last_active_at >= active_since)
    )
    research_runs = store.count_runs()
    root = Path(settings.corpus_dir)
    documents = (
        len([path for path in root.iterdir() if path.is_file() and not path.name.startswith(".")])
        if root.is_dir()
        else None
    )
    transfers = session.scalar(select(func.count()).select_from(LedgerTransfer))
    completed = session.scalar(
        select(func.count())
        .select_from(InvestigationRun)
        .where(InvestigationRun.status == "completed")
    )
    success_rate = None
    if research_runs:
        success_rate = round((completed or 0) / research_runs, 4)
    health = "ok"
    try:
        ping_database()
    except Exception:
        health = "down"
    return AdminOverviewResponse(
        total_users=int(total_users or 0),
        active_users=int(active_users or 0),
        research_runs=int(research_runs),
        documents_indexed=documents,
        transactions_analyzed=int(transfers or 0),
        agent_success_rate=success_rate,
        system_health=health,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(session: Session = Depends(get_session)) -> AdminUserListResponse:
    rows = list(session.scalars(select(AuthUser).order_by(AuthUser.created_at.desc())))
    return AdminUserListResponse(items=[_public(row) for row in rows], total=len(rows))


@router.get("/users/{id}", response_model=PublicUser)
def get_admin_user(id: str, session: Session = Depends(get_session)) -> PublicUser:
    require_id(id, "id")
    user = get_user(session, id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return _public(user)


@router.post("/users/{id}/suspend", response_model=PublicUser)
def suspend_user(
    id: str,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_admin),
) -> PublicUser:
    require_id(id, "id")
    user = get_user(session, id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if user.role == "admin" and count_active_admins(session, exclude_user_id=user.user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot suspend the last active admin.")
    user.status = "suspended"
    revoke_user_sessions(session, user.user_id)
    record_audit(
        session,
        EVENT_USER_SUSPENDED,
        actor_id=actor.user_id,
        resource_id=user.user_id,
        metadata={"target_email": user.email},
    )
    session.commit()
    return _public(user)


@router.post("/users/{id}/activate", response_model=PublicUser)
def activate_user(
    id: str,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_admin),
) -> PublicUser:
    require_id(id, "id")
    user = get_user(session, id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    user.status = "active"
    record_audit(
        session,
        EVENT_USER_ACTIVATED,
        actor_id=actor.user_id,
        resource_id=user.user_id,
        metadata={"target_email": user.email},
    )
    session.commit()
    return _public(user)


@router.post("/users/{id}/role", response_model=PublicUser)
def change_role(
    id: str,
    payload: RoleChangeRequest,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_admin),
) -> PublicUser:
    require_id(id, "id")
    user = get_user(session, id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if (
        user.role == "admin"
        and payload.role == "user"
        and count_active_admins(session, exclude_user_id=user.user_id) == 0
    ):
        raise HTTPException(status_code=400, detail="Cannot remove the last active admin.")
    previous = user.role
    user.role = payload.role
    record_audit(
        session,
        EVENT_ROLE_CHANGED,
        actor_id=actor.user_id,
        resource_id=user.user_id,
        metadata={"from_role": previous, "to_role": payload.role, "target_email": user.email},
    )
    session.commit()
    return _public(user)


@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditListResponse:
    total = int(session.scalar(select(func.count()).select_from(AuditEvent)) or 0)
    rows = list(
        session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit))
    )
    return AuditListResponse(
        total=total,
        items=[
            AuditEventRow(
                event_id=row.event_id,
                actor_id=row.actor_id,
                event_type=row.event_type,
                timestamp=row.created_at,
                resource_id=row.resource_id,
                metadata=row.payload_json or {},
            )
            for row in rows
        ],
    )


@router.get("/research")
def admin_research(store: InvestigationStore = Depends(get_store)) -> dict[str, Any]:
    records = store.list_recent(40)
    return {
        "total": store.count_runs(),
        "items": [
            {
                "investigation_id": item.investigation_id,
                "question": item.question,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "duration_ms": item.duration_ms,
                "input_method": item.input_method,
            }
            for item in records
        ],
    }


@router.get("/documents")
def admin_documents(settings: Settings = Depends(get_app_settings)) -> dict[str, Any]:
    root = Path(settings.corpus_dir)
    documents = []
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                documents.append(
                    {
                        "document_id": path.stem,
                        "name": path.name,
                        "bytes": path.stat().st_size,
                    }
                )
    return {"backend": settings.vector_backend, "documents": documents}


@router.get("/agents", response_model=list[AdminAgentRow])
def admin_agents(session: Session = Depends(get_session)) -> list[AdminAgentRow]:
    rows = list(
        session.scalars(select(InvestigationRun).order_by(InvestigationRun.created_at.desc()))
    )
    stats: dict[str, dict[str, Any]] = {
        key: {"runs": 0, "success": 0, "duration_total": 0, "last": None}
        for key, _label in _AGENT_LABELS
    }
    for row in rows:
        seen: set[str] = set()
        for raw in row.trace_json or []:
            if not isinstance(raw, dict):
                continue
            stage = _stage_for_event(raw)
            if stage is None or stage in seen:
                continue
            seen.add(stage)
            bucket = stats[stage]
            bucket["runs"] += 1
            if row.status == "completed":
                bucket["success"] += 1
            if row.duration_ms is not None:
                bucket["duration_total"] += row.duration_ms
            created = row.created_at
            if bucket["last"] is None or created > bucket["last"]:
                bucket["last"] = created
    result: list[AdminAgentRow] = []
    for key, label in _AGENT_LABELS:
        bucket = stats[key]
        runs = bucket["runs"]
        result.append(
            AdminAgentRow(
                agent=label,
                status="observed" if runs else None,
                runs=runs if rows else None,
                success_rate=round(bucket["success"] / runs, 4) if runs else None,
                average_duration_ms=int(bucket["duration_total"] / runs) if runs else None,
                last_run=bucket["last"],
            )
        )
    return result


@router.get("/ml", response_model=list[AdminMlModelRow])
def admin_ml(session: Session = Depends(get_session)) -> list[AdminMlModelRow]:
    models: list[AdminMlModelRow] = []
    try:
        classified = score_risk(session, "M102", DEFAULT_WINDOW)
        card = classified.card
        models.append(
            AdminMlModelRow(
                model_name="Payment failure classifier",
                task="classification",
                version=card.model_version if card else None,
                dataset_version=card.dataset_version if card else None,
                last_trained=None,
                metrics={
                    "precision": classified.quality.precision,
                    "recall": classified.quality.recall,
                    "f1": classified.quality.f1,
                    "accuracy": classified.quality.accuracy,
                    **(
                        {"roc_auc": classified.quality.roc_auc}
                        if classified.quality.roc_auc is not None
                        else {}
                    ),
                },
                notes=classified.notes,
            )
        )
    except (InsufficientTrainingData, ValueError, LookupError):
        models.append(
            AdminMlModelRow(
                model_name="Payment failure classifier",
                task="classification",
                notes="No data available",
            )
        )
    try:
        regression = score_latency(session, "M102", DEFAULT_WINDOW)
        card = regression.card
        models.append(
            AdminMlModelRow(
                model_name="Capture latency regressor",
                task="regression",
                version=card.model_version if card else None,
                dataset_version=card.dataset_version if card else None,
                last_trained=None,
                metrics={
                    "mae": regression.quality.mae,
                    "rmse": regression.quality.rmse,
                    "r2": regression.quality.r2,
                },
                notes=regression.notes,
            )
        )
    except (InsufficientTrainingData, ValueError, LookupError):
        models.append(
            AdminMlModelRow(
                model_name="Capture latency regressor",
                task="regression",
                notes="No data available",
            )
        )
    return models


@router.get("/transactions", response_model=list[AdminTransactionRow])
def admin_transactions(engine: Engine = Depends(get_engine)) -> list[AdminTransactionRow]:
    transfers = list_recent_transfers(engine, limit=40)
    return [
        AdminTransactionRow(
            transaction_id=item.transfer_id,
            amount_cents=item.amount_cents,
            status=item.status,
            risk_level=None,
            processing_state=item.current_state,
            created_at=None,
        )
        for item in transfers
    ]


@router.get("/transactions/{id}", response_model=AdminTransactionDetail)
def admin_transaction_detail(
    id: str,
    engine: Engine = Depends(get_engine),
    session: Session = Depends(get_session),
) -> AdminTransactionDetail:
    transfer_id = require_id(id, "id")
    transfer = get_transfer(engine, transfer_id)
    if transfer is None:
        payment = session.get(Payment, transfer_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="transaction not found")
        return AdminTransactionDetail(
            transaction_id=payment.payment_id,
            amount_cents=payment.amount_cents,
            status=payment.status,
            risk_level=None,
            processing_state=payment.status,
            created_at=payment.created_at,
            timeline=[],
            risk_analysis=None,
            validation=None,
            audit_events=[],
        )
    row = session.get(LedgerTransfer, transfer_id)
    return AdminTransactionDetail(
        transaction_id=transfer.transfer_id,
        amount_cents=transfer.amount_cents,
        status=transfer.status,
        risk_level=None,
        processing_state=transfer.current_state,
        created_at=row.created_at if row else None,
        timeline=[item.model_dump(mode="json") for item in transfer.operations],
        risk_analysis=None,
        validation=transfer.notes,
        audit_events=[item.model_dump(mode="json") for item in transfer.audit_events],
    )


@router.get("/health")
def admin_health(settings: Settings = Depends(get_app_settings)) -> dict[str, Any]:
    from apps.api.routers.health import services

    body = services(settings)
    return body.model_dump(mode="json")


@router.get("/settings")
def admin_settings(settings: Settings = Depends(get_app_settings)) -> dict[str, Any]:
    return {
        "environment": settings.environment,
        "vector_backend": settings.vector_backend,
        "llm_provider": settings.llm_provider,
        "session_ttl_hours": settings.session_ttl_hours,
        "smtp_configured": bool(settings.smtp_host.strip()),
        "public_app_url": settings.public_app_url,
    }
