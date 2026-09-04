import pytest
from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.models.schemas import MerchantHealthScore
from payops_core.tools.merchant_health import (
    FACTOR_WEIGHTS,
    compute_health_score,
    score_merchant,
)
from sqlalchemy.orm import Session

from tests.health_fixtures import HEALTH_WINDOW, load_health_dataset

HEALTHY_VALUES = {
    "success_rate": 0.98,
    "failure_rate": 0.02,
    "refund_rate": 0.03,
    "dispute_rate": 0.002,
    "webhook_reliability": 0.995,
    "anomaly_severity": 0.05,
}

DEGRADED_VALUES = {
    "success_rate": 0.88,
    "failure_rate": 0.12,
    "refund_rate": 0.12,
    "dispute_rate": 0.02,
    "webhook_reliability": 0.92,
    "anomaly_severity": 0.40,
}

CRITICAL_VALUES = {
    "success_rate": 0.55,
    "failure_rate": 0.42,
    "refund_rate": 0.35,
    "dispute_rate": 0.08,
    "webhook_reliability": 0.65,
    "anomaly_severity": 0.90,
}


def _score(values: dict[str, float], merchant_id: str = "M000") -> MerchantHealthScore:
    return compute_health_score(
        merchant_id=merchant_id,
        factor_values=values,
        window=HEALTH_WINDOW,
        sample_size=100,
    )


def _session() -> Session:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    session = factory()
    load_health_dataset(session)
    session.commit()
    return session


def test_weights_are_explicit_and_sum_to_one() -> None:
    assert set(FACTOR_WEIGHTS) == {
        "success_rate",
        "failure_rate",
        "refund_rate",
        "dispute_rate",
        "webhook_reliability",
        "anomaly_severity",
    }
    assert round(sum(FACTOR_WEIGHTS.values()), 6) == 1.0


def test_healthy_merchant_score() -> None:
    result = _score(HEALTHY_VALUES, "M801")
    reconstructed = round(sum(item.weight * item.score for item in result.factors), 2)
    assert result.score == reconstructed
    assert result.score >= 80
    assert result.band == "healthy"
    assert result.penalties == []
    assert len(result.positive_signals) == len(FACTOR_WEIGHTS)
    assert result.factor_values == HEALTHY_VALUES
    assert [item.name for item in result.factors] == list(FACTOR_WEIGHTS)
    assert result.recommendations == ["No action required; keep monitoring the same factors."]


def test_degraded_merchant_score() -> None:
    result = _score(DEGRADED_VALUES, "M802")
    reconstructed = round(sum(item.weight * item.score for item in result.factors), 2)
    assert result.score == reconstructed
    assert 50 <= result.score < 80
    assert result.band == "degraded"
    assert result.penalties
    assert result.factor_values["failure_rate"] == 0.12
    assert any(item.factor == "failure_rate" for item in result.penalties)
    assert result.recommendations
    assert result.recommendations[0]


def test_critical_merchant_score() -> None:
    result = _score(CRITICAL_VALUES, "M803")
    reconstructed = round(sum(item.weight * item.score for item in result.factors), 2)
    assert result.score == reconstructed
    assert result.score < 50
    assert result.band == "critical"
    assert {item.factor for item in result.penalties} == set(FACTOR_WEIGHTS)
    assert result.positive_signals == []
    joined = " ".join(result.recommendations).lower()
    assert "failure" in joined or "gateway" in joined or "dispute" in joined


def test_same_inputs_yield_the_same_score() -> None:
    first = _score(DEGRADED_VALUES)
    second = _score(DEGRADED_VALUES)
    assert first.score == second.score
    assert first.penalties == second.penalties


def test_fixture_merchants_map_to_bands() -> None:
    session = _session()
    healthy = score_merchant(session, "M801", HEALTH_WINDOW)
    degraded = score_merchant(session, "M802", HEALTH_WINDOW)
    critical = score_merchant(session, "M803", HEALTH_WINDOW)
    assert healthy.band == "healthy"
    assert healthy.score >= 80
    assert healthy.to_evidence().source == "health"
    assert degraded.band == "degraded"
    assert 50 <= degraded.score < 80
    assert critical.band == "critical"
    assert critical.score < 50
    assert any(item.factor == "failure_rate" for item in critical.penalties)
    session.close()


def test_unknown_merchant_raises() -> None:
    session = _session()
    with pytest.raises(LookupError):
        score_merchant(session, "M999", HEALTH_WINDOW)
    session.close()
