from __future__ import annotations

from sqlalchemy.orm import Session

from payops_core.ml.errors import InsufficientTrainingData
from payops_core.ml.select import MlDecision, select_ml_task
from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceItem,
    MerchantRiskScore,
    RegressionScore,
    TimeWindow,
)
from payops_core.tools.ml_risk import score_latency, score_risk


class MLAgent:
    """Select and run classification or regression. Does not write the report."""

    def decide(self, question: str) -> MlDecision:
        return select_ml_task(question)

    def score(
        self,
        session: Session,
        merchant_id: str,
        window: TimeWindow,
    ) -> MerchantRiskScore:
        return score_risk(session, merchant_id, window)

    def regress(
        self,
        session: Session,
        merchant_id: str,
        window: TimeWindow,
    ) -> RegressionScore:
        return score_latency(session, merchant_id, window)

    def run_classification(
        self,
        session: Session,
        merchant_id: str,
        window: TimeWindow,
    ) -> EvidenceBundle:
        try:
            return EvidenceBundle(items=[self.score(session, merchant_id, window).to_evidence()])
        except InsufficientTrainingData as exc:
            return EvidenceBundle(
                items=[
                    _ml_error(
                        merchant_id,
                        "classification",
                        "insufficient_training_data",
                        str(exc),
                    )
                ]
            )

    def run_regression(
        self,
        session: Session,
        merchant_id: str,
        window: TimeWindow,
    ) -> EvidenceBundle:
        try:
            return EvidenceBundle(items=[self.regress(session, merchant_id, window).to_evidence()])
        except InsufficientTrainingData as exc:
            return EvidenceBundle(
                items=[
                    _ml_error(
                        merchant_id,
                        "regression",
                        "insufficient_training_data",
                        str(exc),
                    )
                ]
            )
        except ValueError as exc:
            return EvidenceBundle(
                items=[_ml_error(merchant_id, "regression", "ml_error", str(exc))]
            )


def _ml_error(merchant_id: str, task: str, error: str, detail: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ml-error-{task}-{merchant_id}",
        source="ml",
        text_snippet=detail,
        metadata={"task": task, "error": error, "trainable": False},
    )
