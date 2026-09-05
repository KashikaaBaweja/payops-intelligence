import numpy as np
from payops_core.ml.evaluate import (
    classification_scores,
    regression_mae,
    regression_r2,
    regression_rmse,
    roc_auc_score,
)


def test_failed_class_precision_recall_and_confusion() -> None:
    y_true = np.asarray([1, 1, 0, 0, 0, 0])
    y_pred = np.asarray([1, 0, 1, 0, 0, 0])
    accuracy, precision, recall, f1, support, matrix = classification_scores(y_true, y_pred)
    assert accuracy == 0.6667
    assert support == 2
    assert precision == 0.5
    assert recall == 0.5
    assert f1 == 0.5
    assert matrix.true_positive == 1
    assert matrix.false_positive == 1
    assert matrix.false_negative == 1
    assert matrix.true_negative == 3


def test_roc_auc_perfect_ranking() -> None:
    y_true = np.asarray([1, 1, 0, 0])
    y_score = np.asarray([0.9, 0.8, 0.2, 0.1])
    assert roc_auc_score(y_true, y_score) == 1.0


def test_roc_auc_none_when_one_class_missing() -> None:
    y_true = np.asarray([0, 0, 0])
    y_score = np.asarray([0.1, 0.4, 0.9])
    assert roc_auc_score(y_true, y_score) is None


def test_regression_errors() -> None:
    y_true = np.asarray([10.0, 20.0])
    y_pred = np.asarray([12.0, 16.0])
    assert regression_mae(y_true, y_pred) == 3.0
    assert regression_rmse(y_true, y_pred) == 3.16
    assert regression_r2(np.asarray([1.0, 2.0, 3.0]), np.asarray([1.0, 2.0, 3.0])) == 1.0
