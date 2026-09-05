from payops_core.agents.planner import PlannerAgent
from payops_core.rag.glossary import expand_query


def test_expand_query_adds_english_terms() -> None:
    expanded = expand_query("भुगतान असफल")
    assert "payment" in expanded
    assert "failed" in expanded
    assert expand_query("success rate") == "success rate"


def test_hinglish_glossary_expands_without_replacing_original() -> None:
    original = "Is transaction ka risk kitna hai?"
    expanded = expand_query(original)
    assert expanded.startswith(original)
    assert "how" in expanded.lower()
    assert "much" in expanded.lower()
    assert "risk" in original.lower()


def test_planner_uses_glossary_for_hindi_health() -> None:
    plan = PlannerAgent().plan("M102 स्वास्थ्य")
    assert any(task.task_type == "merchant_health" for task in plan.tasks)
    assert plan.merchant_id == "M102"
