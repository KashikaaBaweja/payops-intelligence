"""Leakage-safe features from the payments table. Status and error_code are labels only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from payops_core.data.models import Payment

METHODS = ("card", "upi", "netbanking", "wallet")
FEATURE_NAMES: tuple[str, ...] = (
    "amount_log",
    "hour",
    "weekday",
    "method_card",
    "method_upi",
    "method_netbanking",
    "method_wallet",
    "merchant_prior_fail_rate",
    "merchant_prior_count_log",
    "merchant_prior_amount_mean_log",
)


@dataclass(frozen=True)
class FeatureRow:
    payment_id: str
    merchant_id: str
    method_id: str
    amount_cents: int
    created_at: datetime
    failed: bool
    latency_seconds: float | None
    values: tuple[float, ...]


def load_feature_rows(session: Session) -> list[FeatureRow]:
    payments = list(
        session.scalars(
            select(Payment).order_by(Payment.created_at.asc(), Payment.payment_id.asc())
        )
    )
    prior: dict[str, list[tuple[bool, int]]] = {}
    rows: list[FeatureRow] = []
    for payment in payments:
        history = prior.setdefault(payment.merchant_id, [])
        fails = sum(1 for failed, _amount in history if failed)
        count = len(history)
        mean_amount = sum(amount for _failed, amount in history) / count if count else 0.0
        values = encode_features(
            amount_cents=payment.amount_cents,
            method_id=payment.method_id,
            created_at=payment.created_at,
            prior_fail_rate=(fails / count) if count else 0.0,
            prior_count=count,
            prior_amount_mean=mean_amount,
        )
        failed = payment.status == "failed"
        latency = None
        if payment.status == "succeeded" and payment.captured_at is not None:
            latency = max(0.0, (payment.captured_at - payment.created_at).total_seconds())
        rows.append(
            FeatureRow(
                payment_id=payment.payment_id,
                merchant_id=payment.merchant_id,
                method_id=payment.method_id,
                amount_cents=payment.amount_cents,
                created_at=payment.created_at,
                failed=failed,
                latency_seconds=latency,
                values=values,
            )
        )
        history.append((failed, payment.amount_cents))
    return rows


def encode_features(
    *,
    amount_cents: int,
    method_id: str,
    created_at: datetime,
    prior_fail_rate: float,
    prior_count: int,
    prior_amount_mean: float,
) -> tuple[float, ...]:
    method = method_id.lower()
    return (
        math.log1p(max(amount_cents, 0)),
        float(created_at.hour),
        float(created_at.weekday()),
        1.0 if method == "card" else 0.0,
        1.0 if method == "upi" else 0.0,
        1.0 if method == "netbanking" else 0.0,
        1.0 if method == "wallet" else 0.0,
        max(0.0, min(1.0, prior_fail_rate)),
        math.log1p(max(prior_count, 0)),
        math.log1p(max(prior_amount_mean, 0.0)),
    )
