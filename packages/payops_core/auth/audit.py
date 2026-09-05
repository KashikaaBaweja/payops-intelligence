from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from payops_core.data.models import AuditEvent

SENSITIVE_KEYS = {
    "password",
    "confirm_password",
    "password_hash",
    "token",
    "reset_token",
    "session_token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "smtp_password",
}

EVENT_SIGNUP = "SIGNUP"
EVENT_LOGIN = "LOGIN"
EVENT_LOGOUT = "LOGOUT"
EVENT_PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
EVENT_PASSWORD_RESET = "PASSWORD_RESET"
EVENT_ROLE_CHANGED = "ROLE_CHANGED"
EVENT_USER_SUSPENDED = "USER_SUSPENDED"
EVENT_USER_ACTIVATED = "USER_ACTIVATED"
EVENT_ADMIN_ACCESS = "ADMIN_ACCESS"
EVENT_DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
EVENT_RESEARCH_STARTED = "RESEARCH_STARTED"
EVENT_RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
EVENT_TRANSACTION_ANALYZED = "TRANSACTION_ANALYZED"


def sanitize_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        lowered = key.lower()
        sensitive = any(part in lowered for part in ("password", "token", "secret"))
        if lowered in SENSITIVE_KEYS or sensitive:
            continue
        if isinstance(value, dict):
            clean[key] = sanitize_metadata(value)
        else:
            clean[key] = value
    return clean


def record_audit(
    session: Session,
    event_type: str,
    *,
    actor_id: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditEvent:
    event = AuditEvent(
        event_id=uuid.uuid4().hex,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        payload_json=sanitize_metadata(metadata),
    )
    session.add(event)
    if commit:
        session.commit()
    return event
