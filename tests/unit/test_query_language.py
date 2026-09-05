from payops_core.agents.planner import PlannerAgent
from payops_core.query_language import (
    detect_query_language,
    language_label,
    resolve_response_language,
    retrieval_query,
    speech_recognition_lang,
)
from payops_core.rag.glossary import expand_query

HINGLISH = "Is transaction ka risk kitna hai?"
ENGLISH = "What is the transaction risk for M102?"
HINDI = "GATEWAY_TIMEOUT का मतलब क्या है?"


def test_detects_english_hindi_and_hinglish() -> None:
    assert detect_query_language("Why did payment failures increase?") == "en"
    assert detect_query_language(HINDI) == "hi"
    assert detect_query_language(HINGLISH) == "hi-latn"
    assert language_label("hi-latn") == "Hindi/Hinglish"


def test_auto_response_language_follows_transcript() -> None:
    assert resolve_response_language(HINGLISH, "auto") == "hi-latn"
    assert resolve_response_language(HINGLISH, "en") == "en"
    assert speech_recognition_lang("hi-latn") == "hi-IN"
    assert speech_recognition_lang("auto", "Why did failures increase?") == "en-IN"


def test_original_query_is_not_replaced_by_expansion() -> None:
    expanded = expand_query(HINGLISH)
    assert expanded.startswith(HINGLISH)
    assert retrieval_query(HINGLISH) == expanded
    assert retrieval_query(ENGLISH) is None


def test_hinglish_and_english_risk_reach_same_planner_tasks() -> None:
    hinglish = PlannerAgent().plan(HINGLISH, merchant_id="M102")
    english = PlannerAgent().plan(ENGLISH, merchant_id="M102")
    assert hinglish.goal == HINGLISH
    assert "score_risk" in {task.task_type for task in hinglish.tasks}
    assert "score_risk" in {task.task_type for task in english.tasks}


def test_english_query_is_not_translated() -> None:
    assert expand_query("What is the payment success rate for M102?") == (
        "What is the payment success rate for M102?"
    )
