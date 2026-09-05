from payops_core.agents.planner import PlannerAgent
from payops_core.ml.select import select_ml_task


def test_success_rate_is_descriptive() -> None:
    assert select_ml_task("What is the payment success rate for M102?") == "descriptive"


def test_predicted_risk_is_classification() -> None:
    assert select_ml_task("What is the predicted payment risk for M102?") == "classification"


def test_capture_latency_is_regression() -> None:
    assert select_ml_task("What is the predicted capture latency for M102?") == "regression"


def test_ml01_question_is_both() -> None:
    question = "What is the predicted payment risk and expected loss for M102?"
    assert select_ml_task(question) == "both"
    types = [task.task_type for task in PlannerAgent().plan(question).tasks]
    assert types == ["score_risk", "query_metrics", "score_regression"]


def test_generic_predict_defaults_to_classification() -> None:
    assert select_ml_task("Predict the next payment for M102") == "classification"


def test_docs_only_question_is_none() -> None:
    assert select_ml_task("What does GATEWAY_TIMEOUT mean?") == "none"
