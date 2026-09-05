from __future__ import annotations

from sqlalchemy.orm import Session

from payops_core.models.schemas import EvidenceBundle, IntegrityAgentResult, Task, TimeWindow
from payops_core.tools.integrity import validate_integrity


class TransactionIntegrityAgent:
    """Validate payment/order consistency. Does not write the final report."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def inspect(
        self,
        question: str,
        window: TimeWindow,
        merchant_id: str | None = None,
        task: Task | None = None,
    ) -> IntegrityAgentResult:
        if task is not None and task.task_type != "validate_integrity":
            raise ValueError("TransactionIntegrityAgent only executes validate_integrity tasks")
        report = validate_integrity(self.session, merchant_id, window)
        return IntegrityAgentResult(
            question=question,
            report=report,
            evidence=EvidenceBundle(items=[report.to_evidence()]),
        )
