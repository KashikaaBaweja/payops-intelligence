from datetime import datetime
from pathlib import Path

import pytest
from payops_core.agents.integrity import TransactionIntegrityAgent
from payops_core.agents.planner import PlannerAgent
from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import Payment
from payops_core.data.seed import seed
from payops_core.models.schemas import Task, TimeWindow
from payops_core.tools.integrity import validate_integrity

WINDOW = TimeWindow(start=datetime(2024, 6, 1), end=datetime(2024, 7, 1))


def _session(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'payops.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    return session_factory(engine)()


def test_seeded_payments_pass_integrity(tmp_path: Path) -> None:
    session = _session(tmp_path)
    report = validate_integrity(session, "M102", WINDOW)
    assert report.passed is True
    assert report.sample_size > 0
    assert all(item.passed for item in report.checks)
    assert "not an ACID commit/rollback" in report.notes
    evidence = report.to_evidence()
    assert evidence.source == "integrity"
    assert evidence.metadata["passed"] is True
    session.close()


def test_missing_captured_at_fails_integrity(tmp_path: Path) -> None:
    session = _session(tmp_path)
    payment = session.query(Payment).filter(Payment.status == "succeeded").first()
    assert payment is not None
    payment.captured_at = None
    session.commit()
    report = validate_integrity(session, payment.merchant_id, WINDOW)
    assert report.passed is False
    capture = next(item for item in report.checks if item.check_id == "succeeded_has_capture")
    assert capture.passed is False
    assert capture.observed >= 1
    session.close()


def test_integrity_agent_rejects_other_tasks(tmp_path: Path) -> None:
    session = _session(tmp_path)
    agent = TransactionIntegrityAgent(session)
    result = agent.inspect("Check ACID invariants for M102", WINDOW, merchant_id="M102")
    assert result.evidence.items[0].source == "integrity"
    with pytest.raises(ValueError, match="validate_integrity"):
        agent.inspect(
            "metrics",
            WINDOW,
            merchant_id="M102",
            task=Task(task_id="t2", task_type="query_metrics", rationale="metrics"),
        )
    session.close()


def test_planner_integrity_question() -> None:
    plan = PlannerAgent().plan(
        "Are Harbor Retail M102 payments transactionally consistent under ACID invariants?"
    )
    assert [task.task_type for task in plan.tasks] == ["validate_integrity"]
    assert plan.merchant_id == "M102"
