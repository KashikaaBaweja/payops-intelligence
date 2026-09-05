from datetime import datetime
from pathlib import Path

import pytest
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.data.seed import seed
from payops_core.ml.errors import InsufficientTrainingData
from payops_core.ml.features import FEATURE_NAMES, encode_features, load_feature_rows
from payops_core.ml.predict import HIGH_THRESHOLD, risk_class_for
from payops_core.ml.train import _split, clear_model_cache, fit_classifier
from payops_core.models.schemas import TimeWindow
from payops_core.tools.ml_risk import score_latency, score_risk, what_if_risk


def _session(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'payops.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    return session_factory(engine)()


def test_features_exclude_label_columns() -> None:
    values = encode_features(
        amount_cents=15000,
        method_id="upi",
        created_at=datetime(2024, 6, 15, 11, 0, 0),
        prior_fail_rate=0.4,
        prior_count=10,
        prior_amount_mean=8000,
    )
    assert len(values) == len(FEATURE_NAMES)
    assert "status" not in FEATURE_NAMES
    assert "error_code" not in FEATURE_NAMES


def test_risk_class_thresholds() -> None:
    assert risk_class_for(0.10) == "LOW"
    assert risk_class_for(0.20) == "MEDIUM"
    assert risk_class_for(HIGH_THRESHOLD) == "HIGH"


def test_score_risk_is_signal_not_decision(tmp_path: Path) -> None:
    clear_model_cache()
    session = _session(tmp_path)
    window = TimeWindow(start=datetime(2024, 6, 1), end=datetime(2024, 7, 1))
    result = score_risk(session, "M102", window)
    session.close()
    assert result.sample_size > 0
    assert 0 <= result.risk_probability <= 1
    assert result.risk_class in {"LOW", "MEDIUM", "HIGH"}
    assert result.prediction in {"failed", "succeeded"}
    assert set(result.class_probabilities) == {"succeeded", "failed"}
    assert result.card is not None
    assert result.card.model_version
    assert result.card.dataset_version
    assert 0 <= result.quality.accuracy <= 1
    assert result.quality.test_size > 0
    assert result.quality.positive_support >= 0
    assert "fraud decision" in result.notes.lower()
    assert result.next_action in {"monitor", "investigate"}
    evidence = result.to_evidence()
    assert evidence.source == "ml"
    assert evidence.metadata["task"] == "classification"
    assert "not a fraud decision" in evidence.text_snippet.lower()


def test_score_latency_is_separate_regression(tmp_path: Path) -> None:
    clear_model_cache()
    session = _session(tmp_path)
    window = TimeWindow(start=datetime(2024, 6, 1), end=datetime(2024, 7, 1))
    result = score_latency(session, "M102", window)
    session.close()
    assert result.target == "capture_latency_seconds"
    assert result.prediction >= 0
    assert result.quality.test_size > 0
    assert result.card.task == "regression"
    evidence = result.to_evidence()
    assert evidence.metadata["task"] == "regression"
    assert "mae" in evidence.metadata
    assert "accuracy" not in evidence.metadata


def test_what_if_amount_change_moves_score(tmp_path: Path) -> None:
    clear_model_cache()
    session = _session(tmp_path)
    high = what_if_risk(session, "M102", method_id="upi", amount_cents=80_000, prior_fail_rate=0.6)
    low = what_if_risk(session, "M102", method_id="card", amount_cents=800, prior_fail_rate=0.02)
    session.close()
    assert high.risk_probability != low.risk_probability
    assert high.contributions
    assert "fraud decision" in high.notes.lower()


def test_split_is_disjoint_and_time_ordered(tmp_path: Path) -> None:
    clear_model_cache()
    session = _session(tmp_path)
    rows = load_feature_rows(session)
    session.close()
    train, test = _split(rows)
    train_ids = {row.payment_id for row in train}
    test_ids = {row.payment_id for row in test}
    assert train_ids.isdisjoint(test_ids)
    assert train[-1].created_at <= test[0].created_at
    assert len(train) + len(test) == len(rows)


def test_fit_classifier_raises_when_training_rows_are_insufficient(tmp_path: Path) -> None:
    clear_model_cache()
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    engine = make_engine(url)
    create_schema(engine)
    session = session_factory(engine)()
    with pytest.raises(InsufficientTrainingData):
        fit_classifier(session)
    session.close()
