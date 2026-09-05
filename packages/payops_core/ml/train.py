"""Train classification and regression separately. Do not mix their metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sqlalchemy.orm import Session

from payops_core.ml.errors import InsufficientTrainingData
from payops_core.ml.evaluate import (
    classification_scores,
    regression_mae,
    regression_r2,
    regression_rmse,
    roc_auc_score,
)
from payops_core.ml.features import FEATURE_NAMES, FeatureRow, load_feature_rows
from payops_core.ml.versioning import dataset_version, model_version
from payops_core.models.schemas import ClassificationQuality, ModelCard, RegressionQuality

MIN_TRAIN_ROWS = 40
_CLASS_CACHE: dict[tuple[int, str, str, int], "FittedClassifier"] = {}
_REG_CACHE: dict[tuple[int, str, str, int], "FittedRegressor"] = {}


@dataclass
class FittedClassifier:
    model: LogisticRegression
    feature_means: tuple[float, ...]
    quality: ClassificationQuality
    card: ModelCard
    train_payment_ids: frozenset[str]


@dataclass
class FittedRegressor:
    model: Ridge
    feature_means: tuple[float, ...]
    quality: RegressionQuality
    card: ModelCard
    target: str
    train_payment_ids: frozenset[str]


def fit_classifier(session: Session) -> FittedClassifier:
    rows = load_feature_rows(session)
    key = _cache_key(rows)
    cached = _CLASS_CACHE.get(key)
    if cached is not None:
        return cached
    if len(rows) < MIN_TRAIN_ROWS:
        raise InsufficientTrainingData(
            f"not enough payments to fit a classifier ({len(rows)} < {MIN_TRAIN_ROWS})"
        )
    fitted = _fit_classifier(rows)
    _CLASS_CACHE[key] = fitted
    return fitted


def fit_regressor(session: Session) -> FittedRegressor:
    rows = [row for row in load_feature_rows(session) if row.latency_seconds is not None]
    key = _cache_key(rows)
    cached = _REG_CACHE.get(key)
    if cached is not None:
        return cached
    if len(rows) < MIN_TRAIN_ROWS:
        raise InsufficientTrainingData(
            f"not enough captured payments to fit capture-latency regression "
            f"({len(rows)} < {MIN_TRAIN_ROWS})"
        )
    fitted = _fit_regressor(rows)
    _REG_CACHE[key] = fitted
    return fitted


def fit_models(session: Session) -> FittedClassifier:
    """Backward-compatible name. Classification only."""
    return fit_classifier(session)


def clear_model_cache() -> None:
    _CLASS_CACHE.clear()
    _REG_CACHE.clear()


def _fit_classifier(rows: list[FeatureRow]) -> FittedClassifier:
    train, test = _split(rows)
    x_train = np.asarray([row.values for row in train], dtype=float)
    y_train = np.asarray([1 if row.failed else 0 for row in train], dtype=int)
    model = LogisticRegression(
        class_weight="balanced",
        max_iter=400,
        random_state=42,
        solver="lbfgs",
    )
    model.fit(x_train, y_train)
    x_test = np.asarray([row.values for row in test], dtype=float)
    y_test = np.asarray([1 if row.failed else 0 for row in test], dtype=int)
    predicted = model.predict(x_test)
    scores = model.predict_proba(x_test)[:, 1]
    accuracy, precision, recall, f1, support, matrix = classification_scores(y_test, predicted)
    data_ver = dataset_version(rows)
    card = ModelCard(
        task="classification",
        algorithm="LogisticRegression",
        target="payment_failed",
        model_version=model_version("logreg-fail", data_ver, len(train)),
        dataset_version=data_ver,
        feature_names=list(FEATURE_NAMES),
        train_rows=len(train),
        test_rows=len(test),
    )
    return FittedClassifier(
        model=model,
        feature_means=tuple(float(value) for value in x_train.mean(axis=0)),
        train_payment_ids=frozenset(row.payment_id for row in train),
        quality=ClassificationQuality(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            roc_auc=roc_auc_score(y_test, scores),
            positive_support=support,
            test_size=len(test),
            confusion_matrix=matrix,
        ),
        card=card,
    )


def _fit_regressor(rows: list[FeatureRow]) -> FittedRegressor:
    train, test = _split(rows)
    x_train = np.asarray([row.values for row in train], dtype=float)
    y_train = np.asarray([float(row.latency_seconds or 0.0) for row in train], dtype=float)
    model = Ridge(alpha=1.0)
    model.fit(x_train, y_train)
    x_test = np.asarray([row.values for row in test], dtype=float)
    y_test = np.asarray([float(row.latency_seconds or 0.0) for row in test], dtype=float)
    predicted = model.predict(x_test)
    data_ver = dataset_version(rows)
    card = ModelCard(
        task="regression",
        algorithm="Ridge",
        target="capture_latency_seconds",
        model_version=model_version("ridge-latency", data_ver, len(train)),
        dataset_version=data_ver,
        feature_names=list(FEATURE_NAMES),
        train_rows=len(train),
        test_rows=len(test),
    )
    return FittedRegressor(
        model=model,
        feature_means=tuple(float(value) for value in x_train.mean(axis=0)),
        train_payment_ids=frozenset(row.payment_id for row in train),
        quality=RegressionQuality(
            mae=regression_mae(y_test, predicted),
            rmse=regression_rmse(y_test, predicted),
            r2=regression_r2(y_test, predicted),
            test_size=len(test),
        ),
        card=card,
        target="capture_latency_seconds",
    )


def _split(rows: list[FeatureRow]) -> tuple[list[FeatureRow], list[FeatureRow]]:
    """Time-ordered holdout. Train and test never share a payment_id."""
    if len(rows) < 2:
        raise InsufficientTrainingData("need at least two rows for a train/test split")
    cut = min(max(1, int(len(rows) * 0.8)), len(rows) - 1)
    train, test = rows[:cut], rows[cut:]
    train_ids = {row.payment_id for row in train}
    test = [row for row in test if row.payment_id not in train_ids]
    if not train or not test:
        raise InsufficientTrainingData("holdout collapsed after de-duplication")
    return train, test


def _cache_key(rows: list[FeatureRow]) -> tuple[int, str, str, int]:
    if not rows:
        return (0, "", "", 0)
    fails = sum(1 for row in rows if row.failed)
    return (len(rows), rows[0].created_at.isoformat(), rows[-1].created_at.isoformat(), fails)


def feature_contributions(
    values: tuple[float, ...],
    coefficients: list[float],
    means: tuple[float, ...],
) -> list[tuple[str, float, float, float]]:
    ranked: list[tuple[str, float, float, float]] = []
    for name, value, coef, mean in zip(FEATURE_NAMES, values, coefficients, means, strict=True):
        ranked.append((name, coef, value, coef * (value - mean)))
    ranked.sort(key=lambda item: abs(item[3]), reverse=True)
    return ranked
