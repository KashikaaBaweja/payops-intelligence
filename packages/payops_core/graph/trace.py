from __future__ import annotations

from payops_core.models.schemas import TraceEvent


def safe_trace(
    *,
    node: str,
    action: str,
    tool: str | None = None,
    search_query: str | None = None,
    evidence_ids: list[str] | None = None,
    decision: str | None = None,
    verification_status: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        node=node,
        action=action,
        tool=tool,
        search_query=search_query,
        evidence_ids=evidence_ids or [],
        decision=decision,
        verification_status=verification_status,
    )
