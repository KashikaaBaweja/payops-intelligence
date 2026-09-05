from pathlib import Path

from payops_core.models.api import InvestigationCreateRequest
from payops_core.query_input import (
    SPEECH_UI_MESSAGES,
    build_research_request,
    normalize_research_query,
    speech_ui_message,
)
from pydantic import ValidationError


def test_typed_query_normalizes_to_query_and_text() -> None:
    assert normalize_research_query("  What does GATEWAY_TIMEOUT mean?  ", "text") == {
        "query": "What does GATEWAY_TIMEOUT mean?",
        "input_method": "text",
        "language": "auto",
    }


def test_voice_transcript_normalizes_to_same_shape() -> None:
    assert normalize_research_query("What does GATEWAY_TIMEOUT mean?", "voice") == {
        "query": "What does GATEWAY_TIMEOUT mean?",
        "input_method": "voice",
        "language": "auto",
    }


def test_edited_voice_transcript_uses_edited_text() -> None:
    spoken = "settlement delays"
    edited = "Why did settlement delays increase for Harbor Retail M102?"
    assert normalize_research_query(edited, "voice") == {
        "query": edited,
        "input_method": "voice",
        "language": "auto",
    }
    assert normalize_research_query(spoken, "voice") != normalize_research_query(edited, "voice")


def test_empty_transcript_builds_no_request() -> None:
    assert normalize_research_query("", "voice") is None
    assert normalize_research_query("  ", "voice") is None
    assert normalize_research_query("no", "text") is None
    assert build_research_request("", "voice") is None
    assert build_research_request("hi", "text") is None


def test_build_research_request_for_typed_and_voice() -> None:
    typed = build_research_request("What does GATEWAY_TIMEOUT mean?", "text", "M102")
    voice = build_research_request("What does GATEWAY_TIMEOUT mean?", "voice", "M102")
    assert typed is not None and voice is not None
    assert typed["query"] == voice["query"]
    assert typed["input_method"] == "text"
    assert voice["input_method"] == "voice"
    assert typed["merchant_id"] == "M102"
    assert typed["language"] == "auto"
    hinglish = build_research_request(
        "Is transaction ka risk kitna hai?",
        "voice",
        "M102",
        3,
        "hi-latn",
    )
    assert hinglish is not None
    assert hinglish["query"] == "Is transaction ka risk kitna hai?"
    assert hinglish["language"] == "hi-latn"


def test_create_request_accepts_query_or_question_alias() -> None:
    by_query = InvestigationCreateRequest(
        query="What does GATEWAY_TIMEOUT mean?",
        input_method="voice",
    )
    by_question = InvestigationCreateRequest(question="What does GATEWAY_TIMEOUT mean?")
    assert by_query.query == by_question.query == by_question.question
    assert by_query.input_method == "voice"
    assert by_question.input_method == "text"


def test_create_request_rejects_empty_transcript() -> None:
    try:
        InvestigationCreateRequest(query="", input_method="voice")
    except ValidationError:
        return
    raise AssertionError("empty voice query must not validate")


def test_speech_recognition_failure_is_recoverable() -> None:
    for code in (
        "not-supported",
        "not-allowed",
        "no-speech",
        "unavailable",
        "network",
        "unknown-code",
    ):
        message = speech_ui_message(code)
        assert message
        assert "audio file" not in message.lower()
        assert any(token in message.lower() for token in ("type", "tap", "try again", "instead"))
    assert SPEECH_UI_MESSAGES["not-allowed"] == speech_ui_message("not-allowed")
    assert build_research_request("", "voice") is None


def test_landing_analyze_href_starts_real_research() -> None:
    source = Path("apps/web/lib/queryInput.ts").read_text()
    ask = Path("apps/web/components/landing/LandingAsk.tsx").read_text()
    assert "buildLandingAnalyzeHref" in source
    assert 'run: "1"' in source
    assert "/research?" in source
    assert "buildLandingAnalyzeHref" in ask
    assert "MediaRecorder" not in ask
    assert "Why are settlement delays increasing?" not in ask
    assert "18.7" not in ask
    assert "Tap to speak" in ask
    hook = Path("apps/web/lib/useSpeechQuery.ts").read_text()
    assert "HOLD_MS" in hook
    assert 'event.key.toLowerCase() !== "v"' in hook
    dashboard = Path("apps/web/components/Dashboard.tsx").read_text()
    assert "Why this result?" in dashboard
    assert "autoRunOnce" in dashboard
    assert "18.7" not in dashboard


def test_speech_module_does_not_store_audio() -> None:
    source = Path("apps/web/lib/speech.ts").read_text()
    history = Path("apps/web/components/research/QueryHistory.tsx").read_text()
    assert "MediaRecorder" not in source
    assert "localStorage" not in source
    assert "MediaRecorder" not in history
    assert "audio" not in history.lower() or "audio is never stored" in history.lower()
    for code in SPEECH_UI_MESSAGES:
        assert code in source
