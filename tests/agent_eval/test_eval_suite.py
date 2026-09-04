from payops_core.eval.dataset import CASES, all_categories
from payops_core.eval.harness import run_suite
from payops_core.eval.schema import Category


def test_dataset_covers_required_scope() -> None:
    assert len(CASES) >= 25
    expected = set(Category.__args__)  # type: ignore[attr-defined]
    assert all_categories() == expected


def test_evaluation_suite_meets_pass_bar(tmp_path) -> None:
    report = run_suite(database_url=f"sqlite:///{tmp_path / 'eval.db'}")
    assert report.case_count == len(CASES)
    failed = [item.case_id for item in report.cases if not item.passed]
    assert failed == []
