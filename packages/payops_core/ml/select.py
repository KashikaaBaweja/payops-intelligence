"""Choose classification, regression, descriptive analysis, or no ML."""

from __future__ import annotations

import re
from typing import Literal

from payops_core.rag.glossary import expand_query

MlDecision = Literal["classification", "regression", "both", "descriptive", "none"]

_TOKEN = re.compile(r"[a-z0-9_]+")
_CLASS = frozenset(
    {
        "risk",
        "risky",
        "fraud",
        "classifier",
        "classify",
        "classification",
        "class",
        "outcome",
        "probability",
        "auc",
        "precision",
        "recall",
    }
)
_PREDICT = frozenset({"predict", "predicted", "prediction", "ml"})
_REGRESS = frozenset(
    {
        "loss",
        "amount",
        "delay",
        "latency",
        "processing",
        "settlement",
        "regress",
        "regression",
        "mae",
        "rmse",
        "expected",
    }
)
_DESCRIBE = frozenset(
    {
        "rate",
        "success",
        "metric",
        "metrics",
        "breakdown",
        "volume",
        "compare",
        "health",
        "scorecard",
    }
)


def select_ml_task(question: str) -> MlDecision:
    tokens = set(_TOKEN.findall(expand_query(question).lower()))
    wants_class = bool(tokens & _CLASS)
    wants_reg = bool(tokens & _REGRESS)
    if wants_class and wants_reg:
        return "both"
    if wants_class:
        return "classification"
    if wants_reg:
        return "regression"
    if tokens & _PREDICT:
        return "classification"
    if tokens & _DESCRIBE:
        return "descriptive"
    return "none"
