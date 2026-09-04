from __future__ import annotations

import re

from sqlalchemy.orm import Session

from payops_core.data.models import Merchant
from payops_core.models.schemas import (
    AnalyticsRequest,
    HealthFactor,
    HealthPenalty,
    MerchantHealthScore,
    TimeWindow,
)
from payops_core.tools.sql_gateway import SqlToolGateway

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Weights are public so a reviewer can recompute the score from factor_values.
FACTOR_WEIGHTS: dict[str, float] = {
    "success_rate": 0.20,
    "failure_rate": 0.20,
    "refund_rate": 0.10,
    "dispute_rate": 0.20,
    "webhook_reliability": 0.15,
    "anomaly_severity": 0.15,
}

# (healthy, critical, higher_is_better)
FACTOR_BOUNDS: dict[str, tuple[float, float, bool]] = {
    "success_rate": (0.95, 0.70, True),
    "failure_rate": (0.05, 0.30, False),
    "refund_rate": (0.08, 0.30, False),
    "dispute_rate": (0.01, 0.05, False),
    "webhook_reliability": (0.97, 0.80, True),
    "anomaly_severity": (0.15, 0.75, False),
}

_RECOMMENDATIONS = {
    "success_rate": "Investigate method-level success and fail over the affected processor.",
    "failure_rate": (
        "Break down failures by error code and page the processor if GATEWAY_TIMEOUT dominates."
    ),
    "refund_rate": "Review recent refund reasons against the refund policy.",
    "dispute_rate": "Triage open disputes and gather evidence packs.",
    "webhook_reliability": (
        "Inspect failed and delayed webhook deliveries; do not treat delays as declines."
    ),
    "anomaly_severity": (
        "Compare this window to the prior window and check for a concentrated error-code spike."
    ),
    "volume": "Widen the time window or confirm the merchant is processing payments.",
}


def compute_health_score(
    *,
    merchant_id: str,
    factor_values: dict[str, float],
    window: TimeWindow | None = None,
    sample_size: int = 0,
) -> MerchantHealthScore:
    """Score from named metrics only. No model weights are learned."""

    if sample_size == 0:
        return _empty_score(merchant_id, window)
    factors: list[HealthFactor] = []
    penalties: list[HealthPenalty] = []
    positives: list[str] = []
    total = 0.0
    for name, weight in FACTOR_WEIGHTS.items():
        value = float(factor_values[name])
        ratio = _penalty_ratio(name, value)
        factor_score = round(100.0 * (1.0 - ratio), 2)
        band = _factor_band(ratio)
        total += weight * factor_score
        explanation = _explain(name, value, factor_score, band)
        factors.append(
            HealthFactor(
                name=name,
                weight=weight,
                value=value,
                score=factor_score,
                band=band,
                explanation=explanation,
            )
        )
        if ratio > 0:
            penalties.append(
                HealthPenalty(
                    factor=name,
                    points=round(weight * 100.0 * ratio, 2),
                    reason=explanation,
                )
            )
        else:
            positives.append(explanation)
    score = round(total, 2)
    band = _score_band(score)
    recommendations = [
        _RECOMMENDATIONS[item.factor]
        for item in sorted(penalties, key=lambda item: item.points, reverse=True)
        if item.factor in _RECOMMENDATIONS
    ]
    if not recommendations:
        recommendations = ["No action required; keep monitoring the same factors."]
    return MerchantHealthScore(
        merchant_id=merchant_id,
        window=window,
        score=score,
        band=band,
        factors=factors,
        factor_values={name: float(factor_values[name]) for name in FACTOR_WEIGHTS},
        penalties=penalties,
        positive_signals=positives,
        recommendations=recommendations,
    )


def score_merchant(
    session: Session,
    merchant_id: str,
    window: TimeWindow,
) -> MerchantHealthScore:
    if not _ID.match(merchant_id):
        raise ValueError("invalid merchant_id")
    merchant = session.get(Merchant, merchant_id)
    if merchant is None:
        raise LookupError(f"unknown merchant_id: {merchant_id}")
    values, sample_size = collect_factor_values(session, merchant_id, window)
    return compute_health_score(
        merchant_id=merchant_id,
        factor_values=values,
        window=window,
        sample_size=sample_size,
    )


def collect_factor_values(
    session: Session,
    merchant_id: str,
    window: TimeWindow,
) -> tuple[dict[str, float], int]:
    gateway = SqlToolGateway(session)
    success = gateway.run(_request("get_success_rate", merchant_id, window))
    failure = gateway.run(_request("get_failure_rate", merchant_id, window))
    refunds = gateway.run(_request("get_refund_rate", merchant_id, window))
    disputes = gateway.run(_request("get_dispute_rate", merchant_id, window))
    webhooks = gateway.run(_request("get_webhook_failure_rate", merchant_id, window))
    previous = previous_window(window)
    prior_failure = gateway.run(_request("get_failure_rate", merchant_id, previous))
    errors = gateway.run(_request("breakdown_by_error_code", merchant_id, window))
    gateway_share = 0.0
    if isinstance(errors.value, dict) and "GATEWAY_TIMEOUT" in errors.value:
        gateway_share = float(errors.value["GATEWAY_TIMEOUT"].get("share") or 0.0)
    current_failure = float(failure.value)
    prior_value = float(prior_failure.value)
    if (prior_failure.sample_size or 0) == 0:
        spike = min(1.0, current_failure / 0.25) if current_failure else 0.0
    else:
        spike = min(1.0, max(0.0, current_failure - prior_value) / 0.20)
    reliability = round(1.0 - float(webhooks.value), 6)
    anomaly = round(min(1.0, 0.6 * spike + 0.4 * gateway_share), 6)
    values = {
        "success_rate": float(success.value),
        "failure_rate": current_failure,
        "refund_rate": float(refunds.value),
        "dispute_rate": float(disputes.value),
        "webhook_reliability": reliability,
        "anomaly_severity": anomaly,
    }
    return values, int(success.sample_size or 0)


def _request(operation: str, merchant_id: str, window: TimeWindow) -> AnalyticsRequest:
    return AnalyticsRequest(
        operation=operation,  # type: ignore[arg-type]
        window=window,
        merchant_id=merchant_id,
    )


def _penalty_ratio(name: str, value: float) -> float:
    healthy, critical, higher_is_better = FACTOR_BOUNDS[name]
    if higher_is_better:
        if value >= healthy:
            return 0.0
        if value <= critical:
            return 1.0
        return (healthy - value) / (healthy - critical)
    if value <= healthy:
        return 0.0
    if value >= critical:
        return 1.0
    return (value - healthy) / (critical - healthy)


def _factor_band(ratio: float) -> str:
    if ratio <= 0:
        return "healthy"
    if ratio < 0.5:
        return "degraded"
    return "critical"


def _score_band(score: float) -> str:
    if score >= 80:
        return "healthy"
    if score >= 50:
        return "degraded"
    return "critical"


def _explain(name: str, value: float, factor_score: float, band: str) -> str:
    display = f"{value:.2%}" if name != "anomaly_severity" else f"{value:.2f}"
    return (
        f"{name}={display} scores {factor_score:.0f}/100 "
        f"(weight {FACTOR_WEIGHTS[name]:.0%}, {band})"
    )


def _empty_score(merchant_id: str, window: TimeWindow | None) -> MerchantHealthScore:
    values = {name: 0.0 for name in FACTOR_WEIGHTS}
    factors = [
        HealthFactor(
            name=name,
            weight=weight,
            value=0.0,
            score=0.0,
            band="critical",
            explanation="No payments in the window",
        )
        for name, weight in FACTOR_WEIGHTS.items()
    ]
    return MerchantHealthScore(
        merchant_id=merchant_id,
        window=window,
        score=0.0,
        band="critical",
        factors=factors,
        factor_values=values,
        penalties=[
            HealthPenalty(
                factor="volume",
                points=100.0,
                reason="No payments in the window",
            )
        ],
        positive_signals=[],
        recommendations=[_RECOMMENDATIONS["volume"]],
    )


def previous_window(window: TimeWindow) -> TimeWindow:
    delta = window.end - window.start
    return TimeWindow(start=window.start - delta, end=window.start)
