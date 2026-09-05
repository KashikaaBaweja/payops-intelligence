"""Catalog entry for the payment-risk models. Agents never train or invent features."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from payops_core.ml.predict import score_capture_latency, score_merchant_risk, score_what_if
from payops_core.models.schemas import (
    MerchantRiskScore,
    RegressionScore,
    RiskWhatIfScore,
    TimeWindow,
)

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def score_risk(session: Session, merchant_id: str, window: TimeWindow) -> MerchantRiskScore:
    if not _ID.match(merchant_id):
        raise ValueError("invalid merchant_id")
    if window.end <= window.start:
        raise ValueError("time window end must be after start")
    return score_merchant_risk(session, merchant_id, window)


def score_latency(session: Session, merchant_id: str, window: TimeWindow) -> RegressionScore:
    if not _ID.match(merchant_id):
        raise ValueError("invalid merchant_id")
    if window.end <= window.start:
        raise ValueError("time window end must be after start")
    return score_capture_latency(session, merchant_id, window)


def what_if_risk(
    session: Session,
    merchant_id: str,
    *,
    method_id: str,
    amount_cents: int,
    hour: int | None = None,
    weekday: int | None = None,
    prior_fail_rate: float | None = None,
) -> RiskWhatIfScore:
    if not _ID.match(merchant_id):
        raise ValueError("invalid merchant_id")
    return score_what_if(
        session,
        merchant_id,
        method_id=method_id,
        amount_cents=amount_cents,
        hour=hour,
        weekday=weekday,
        prior_fail_rate=prior_fail_rate,
    )
