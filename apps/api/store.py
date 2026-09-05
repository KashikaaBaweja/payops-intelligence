from __future__ import annotations

from datetime import datetime, timezone

from payops_core.data.models import EvidenceIndex, InvestigationRun
from payops_core.models.schemas import EvidenceItem, IncidentReport, TraceEvent
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session


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
        input_method: str = "text",
        duration_ms: int | None = None,
    ) -> None:
        self.investigation_id = investigation_id
        self.question = question
        self.input_method = "voice" if input_method == "voice" else "text"
        self.status = status
        self.report = report
        self.trace = trace
        self.evidence = evidence
        self.error = error
        self.created_at = created_at or datetime.now(timezone.utc)
        self.duration_ms = duration_ms if duration_ms is None or duration_ms >= 0 else None


class InvestigationStore:
    """Postgres/SQLite-backed investigation and evidence index."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def put(self, record: StoredInvestigation) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row = self.session.get(InvestigationRun, record.investigation_id)
        if row is None:
            row = InvestigationRun(
                investigation_id=record.investigation_id,
                question=record.question,
                input_method=record.input_method,
                status=record.status,
                created_at=record.created_at.replace(tzinfo=None)
                if record.created_at.tzinfo
                else record.created_at,
            )
            self.session.add(row)
        row.question = record.question
        row.input_method = record.input_method
        row.status = record.status
        row.merchant_id = record.report.merchant_id if record.report else None
        row.report_json = record.report.model_dump(mode="json") if record.report else None
        row.trace_json = [event.model_dump(mode="json") for event in record.trace]
        row.error = record.error
        row.duration_ms = record.duration_ms
        row.updated_at = now
        for item in record.evidence:
            self._upsert_evidence(item, record.investigation_id)
        self.session.commit()

    def list_recent(self, limit: int = 20) -> list[StoredInvestigation]:
        rows = list(
            self.session.scalars(
                select(InvestigationRun).order_by(InvestigationRun.created_at.desc()).limit(limit)
            )
        )
        if not rows:
            return []
        ids = [row.investigation_id for row in rows]
        evidence_rows = list(
            self.session.scalars(
                select(EvidenceIndex).where(EvidenceIndex.investigation_id.in_(ids))
            )
        )
        by_run: dict[str, list[EvidenceItem]] = {item: [] for item in ids}
        for item in evidence_rows:
            if item.investigation_id:
                by_run.setdefault(item.investigation_id, []).append(
                    EvidenceItem.model_validate(item.payload_json)
                )
        return [self._from_row(row, by_run.get(row.investigation_id, [])) for row in rows]

    def count_runs(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(InvestigationRun)) or 0)

    def count_evidence(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(EvidenceIndex)) or 0)

    def delete(self, investigation_id: str) -> bool:
        row = self.session.get(InvestigationRun, investigation_id)
        if row is None:
            return False
        self.session.execute(
            delete(EvidenceIndex).where(EvidenceIndex.investigation_id == investigation_id)
        )
        self.session.delete(row)
        self.session.commit()
        return True

    def delete_all(self) -> int:
        ids = list(self.session.scalars(select(InvestigationRun.investigation_id)))
        if ids:
            self.session.execute(
                delete(EvidenceIndex).where(EvidenceIndex.investigation_id.in_(ids))
            )
        deleted = len(ids)
        self.session.execute(delete(InvestigationRun))
        self.session.commit()
        return deleted

    def get(self, investigation_id: str) -> StoredInvestigation | None:
        row = self.session.get(InvestigationRun, investigation_id)
        if row is None:
            return None
        evidence_rows = self.session.scalars(
            select(EvidenceIndex).where(EvidenceIndex.investigation_id == investigation_id)
        )
        evidence = [EvidenceItem.model_validate(item.payload_json) for item in evidence_rows]
        return self._from_row(row, evidence)

    def _from_row(self, row: InvestigationRun, evidence: list[EvidenceItem]) -> StoredInvestigation:
        duration_ms = getattr(row, "duration_ms", None)
        if duration_ms is None and row.created_at and row.updated_at:
            delta = (row.updated_at - row.created_at).total_seconds()
            if delta >= 0:
                duration_ms = int(delta * 1000)
        return StoredInvestigation(
            investigation_id=row.investigation_id,
            question=row.question,
            input_method=getattr(row, "input_method", None) or "text",
            status=row.status,
            report=IncidentReport.model_validate(row.report_json) if row.report_json else None,
            trace=[TraceEvent.model_validate(event) for event in (row.trace_json or [])],
            evidence=evidence,
            error=row.error,
            created_at=row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at,
            duration_ms=duration_ms,
        )

    def index_evidence(self, items: list[EvidenceItem]) -> None:
        for item in items:
            self._upsert_evidence(item, None)
        self.session.commit()

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        row = self.session.get(EvidenceIndex, evidence_id)
        if row is None:
            return None
        return EvidenceItem.model_validate(row.payload_json)

    def _upsert_evidence(self, item: EvidenceItem, investigation_id: str | None) -> None:
        row = self.session.get(EvidenceIndex, item.evidence_id)
        payload = item.model_dump(mode="json")
        if row is None:
            self.session.add(
                EvidenceIndex(
                    evidence_id=item.evidence_id,
                    investigation_id=investigation_id,
                    payload_json=payload,
                )
            )
            return
        if investigation_id is None and row.investigation_id:
            return
        row.payload_json = payload
        if investigation_id:
            row.investigation_id = investigation_id
