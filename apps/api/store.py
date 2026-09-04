from __future__ import annotations

import threading
from datetime import datetime, timezone

from payops_core.models.schemas import EvidenceItem, IncidentReport, TraceEvent


class StoredInvestigation:
    def __init__(
        self,
        investigation_id: str,
        question: str,
        status: str,
        report: IncidentReport | None,
        trace: list[TraceEvent],
        evidence: list[EvidenceItem],
        error: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.investigation_id = investigation_id
        self.question = question
        self.status = status
        self.report = report
        self.trace = trace
        self.evidence = evidence
        self.error = error
        self.created_at = created_at or datetime.now(timezone.utc)


class InvestigationStore:
    """Process-local investigation and evidence index. Not a durable database."""

    def __init__(self) -> None:
        self._items: dict[str, StoredInvestigation] = {}
        self._evidence: dict[str, EvidenceItem] = {}
        self._lock = threading.Lock()

    def put(self, record: StoredInvestigation) -> None:
        with self._lock:
            self._items[record.investigation_id] = record
            for item in record.evidence:
                self._evidence[item.evidence_id] = item

    def get(self, investigation_id: str) -> StoredInvestigation | None:
        with self._lock:
            return self._items.get(investigation_id)

    def index_evidence(self, items: list[EvidenceItem]) -> None:
        with self._lock:
            for item in items:
                self._evidence[item.evidence_id] = item

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        with self._lock:
            return self._evidence.get(evidence_id)
