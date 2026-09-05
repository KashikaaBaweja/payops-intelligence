"""Holdout metrics computed from predictions. Never invent scores."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from payops_core.models.schemas import ConfusionMatrix


def classification_scores(
    y_true: NDArray[np.int_],
    y_pred: NDArray[np.int_],
) -> tuple[float, float, float, float, int, ConfusionMatrix]:
    true_pos = int(np.sum((y_true == 1) & (y_pred == 1)))
    false_pos = int(np.sum((y_true == 0) & (y_pred == 1)))
    false_neg = int(np.sum((y_true == 1) & (y_pred == 0)))
    true_neg = int(np.sum((y_true == 0) & (y_pred == 0)))
    support = int(np.sum(y_true == 1))
    total = int(y_true.size)
    accuracy = (true_pos + true_neg) / total if total else 0.0
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 0.0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    matrix = ConfusionMatrix(
        true_negative=true_neg,
        false_positive=false_pos,
        false_negative=false_neg,
        true_positive=true_pos,
    )
    return (
        round(accuracy, 4),
        round(precision, 4),
        round(recall, 4),
        round(f1, 4),
        support,
        matrix,
    )


def roc_auc_score(y_true: NDArray[np.int_], y_score: NDArray[np.float64]) -> float | None:
    positives = int(np.sum(y_true == 1))
    negatives = int(np.sum(y_true == 0))
    if positives == 0 or negatives == 0:
        return None
    ranks = np.argsort(np.argsort(y_score))
    pos_rank_sum = float(np.sum(ranks[y_true == 1]))
    auc = (pos_rank_sum - positives * (positives - 1) / 2.0) / (positives * negatives)
    return round(float(auc), 4)


def regression_mae(y_true: NDArray[np.float64], y_pred: NDArray[np.float64]) -> float:
    if y_true.size == 0:
        return 0.0
    return round(float(np.mean(np.abs(y_true - y_pred))), 2)


def regression_rmse(y_true: NDArray[np.float64], y_pred: NDArray[np.float64]) -> float:
    if y_true.size == 0:
        return 0.0
    return round(float(np.sqrt(np.mean((y_true - y_pred) ** 2))), 2)


def regression_r2(y_true: NDArray[np.float64], y_pred: NDArray[np.float64]) -> float:
    if y_true.size == 0:
        return 0.0
    mean = float(np.mean(y_true))
    total = float(np.sum((y_true - mean) ** 2))
    if total == 0:
        return 0.0
    residual = float(np.sum((y_true - y_pred) ** 2))
    return round(1.0 - (residual / total), 4)
