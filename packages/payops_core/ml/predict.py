from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from payops_core.ml.features import FEATURE_NAMES, encode_features, load_feature_rows
from payops_core.ml.train import feature_contributions, fit_classifier, fit_regressor
from payops_core.models.schemas import (
    MerchantRiskScore,
    RegressionScore,
    RiskContribution,
    RiskWhatIfScore,
    TimeWindow,
)

HIGH_THRESHOLD = 0.35
MEDIUM_THRESHOLD = 0.15
_CLASS_NOTE = (
    "Classification signal only. Do not treat this as a fraud decision. "
    "Quality metrics are a global time-ordered holdout, not the scored window. "
    "Investigate metrics and runbooks before naming a cause."
)
_REG_NOTE = (
    "Ridge regression on capture latency (captured_at − created_at) for succeeded payments. "
    "Quality metrics are a global time-ordered holdout, not the scored window. "
    "Constant synthetic capture times produce a low R²."
)
_TRAIN_OVERLAP_NOTE = " Window payments overlapped the training set; those rows were excluded."


def risk_class_for(probability: float) -> str:
    if probability >= HIGH_THRESHOLD:
        return "HIGH"
    if probability >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def score_merchant_risk(
    session: Session,
    merchant_id: str,
    window: TimeWindow,
) -> MerchantRiskScore:
    fitted = fit_classifier(session)
    in_window = [
        row
        for row in load_feature_rows(session)
        if row.merchant_id == merchant_id and window.start <= row.created_at < window.end
    ]
    rows = [row for row in in_window if row.payment_id not in fitted.train_payment_ids]
    if not rows:
        note = (
            "Window payments were used in training. Holdout score withheld to avoid leakage."
            if in_window
            else "No payments in the window. Classifier was not applied to a cohort."
        )
        return MerchantRiskScore(
            merchant_id=merchant_id,
            window=window,
            sample_size=0,
            fail_count=0,
            prediction="succeeded",
            risk_probability=0.0,
            class_probabilities={"succeeded": 1.0, "failed": 0.0},
            risk_class="LOW",
            features={},
            contributions=[],
            quality=fitted.quality,
            card=fitted.card,
            next_action="monitor",
            notes=note,
        )
    matrix = [list(row.values) for row in rows]
    probabilities = fitted.model.predict_proba(matrix)[:, 1]
    mean_p = float(sum(probabilities) / len(probabilities))
    band = risk_class_for(mean_p)
    mean_values = tuple(
        sum(row.values[index] for row in rows) / len(rows) for index in range(len(FEATURE_NAMES))
    )
    features = {
        name: round(value, 4) for name, value in zip(FEATURE_NAMES, mean_values, strict=True)
    }
    coefs = [float(value) for value in fitted.model.coef_[0]]
    return MerchantRiskScore(
        merchant_id=merchant_id,
        window=window,
        sample_size=len(rows),
        fail_count=sum(1 for row in rows if row.failed),
        prediction="failed" if mean_p >= 0.5 else "succeeded",
        risk_probability=round(mean_p, 4),
        class_probabilities={
            "succeeded": round(1.0 - mean_p, 4),
            "failed": round(mean_p, 4),
        },
        risk_class=band,  # type: ignore[arg-type]
        features=features,
        contributions=_contributions(mean_values, coefs, fitted.feature_means, "log-odds"),
        quality=fitted.quality,
        card=fitted.card,
        next_action="investigate" if band == "HIGH" else "monitor",
        notes=_CLASS_NOTE + (_TRAIN_OVERLAP_NOTE if len(rows) < len(in_window) else ""),
    )


def score_capture_latency(
    session: Session,
    merchant_id: str,
    window: TimeWindow,
) -> RegressionScore:
    fitted = fit_regressor(session)
    in_window = [
        row
        for row in load_feature_rows(session)
        if row.merchant_id == merchant_id
        and window.start <= row.created_at < window.end
        and row.latency_seconds is not None
    ]
    rows = [row for row in in_window if row.payment_id not in fitted.train_payment_ids]
    if not rows:
        raise ValueError(
            "no out-of-sample captured payments in the window for latency regression"
        )
    matrix = [list(row.values) for row in rows]
    predicted = fitted.model.predict(matrix)
    mean_hat = float(sum(predicted) / len(predicted))
    mean_values = tuple(
        sum(row.values[index] for row in rows) / len(rows) for index in range(len(FEATURE_NAMES))
    )
    features = {
        name: round(value, 4) for name, value in zip(FEATURE_NAMES, mean_values, strict=True)
    }
    coefs = [float(value) for value in fitted.model.coef_]
    return RegressionScore(
        merchant_id=merchant_id,
        window=window,
        sample_size=len(rows),
        target=fitted.target,
        prediction=round(mean_hat, 4),
        features=features,
        contributions=_contributions(mean_values, coefs, fitted.feature_means, "latency seconds"),
        quality=fitted.quality,
        card=fitted.card,
        notes=_REG_NOTE + (_TRAIN_OVERLAP_NOTE if len(rows) < len(in_window) else ""),
    )


def score_what_if(
    session: Session,
    merchant_id: str,
    *,
    method_id: str,
    amount_cents: int,
    hour: int | None = None,
    weekday: int | None = None,
    prior_fail_rate: float | None = None,
) -> RiskWhatIfScore:
    fitted = fit_classifier(session)
    history = [
        row
        for row in load_feature_rows(session)
        if row.merchant_id == merchant_id and row.payment_id not in fitted.train_payment_ids
    ]
    fail_rate = (
        prior_fail_rate
        if prior_fail_rate is not None
        else ((sum(1 for row in history if row.failed) / len(history)) if history else 0.0)
    )
    mean_amount = (
        sum(row.amount_cents for row in history) / len(history) if history else float(amount_cents)
    )
    hour_value = 11 if hour is None else hour
    weekday_value = 5 if weekday is None else weekday
    created = datetime(2024, 6, 10 + weekday_value, hour_value, 0, 0)
    values = encode_features(
        amount_cents=amount_cents,
        method_id=method_id,
        created_at=created,
        prior_fail_rate=fail_rate,
        prior_count=len(history),
        prior_amount_mean=mean_amount,
    )
    probability = float(fitted.model.predict_proba([list(values)])[0, 1])
    band = risk_class_for(probability)
    coefs = [float(value) for value in fitted.model.coef_[0]]
    return RiskWhatIfScore(
        merchant_id=merchant_id,
        method_id=method_id,
        amount_cents=amount_cents,
        risk_probability=round(probability, 4),
        risk_class=band,  # type: ignore[arg-type]
        expected_loss_cents=0,
        contributions=_contributions(values, coefs, fitted.feature_means, "log-odds"),
        next_action="investigate" if band == "HIGH" else "monitor",
        notes=_CLASS_NOTE,
    )


def _contributions(
    values: tuple[float, ...],
    coefficients: list[float],
    means: tuple[float, ...],
    unit: str,
) -> list[RiskContribution]:
    return [
        RiskContribution(
            feature=name,
            coefficient=round(coef, 4),
            value=round(value, 4),
            contribution=round(contrib, 4),
            explanation=f"{name} contributes {contrib:+.3f} to {unit} vs the train mean",
        )
        for name, coef, value, contrib in feature_contributions(values, coefficients, means)[:5]
    ]
