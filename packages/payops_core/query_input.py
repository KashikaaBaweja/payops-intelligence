"""Normalize typed and voice research input into one query payload.

Voice is an input modality only. The graph always receives the same
normalized query string; it never sees audio or a separate voice agent.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from payops_core.query_language import LanguageChoice, normalize_language_choice

InputMethod = Literal["text", "voice"]
MIN_QUERY_LEN = 3
MAX_QUERY_LEN = 4000

SPEECH_UI_MESSAGES = {
    "not-supported": "This browser does not support tap-to-speak. Type the question instead.",
    "not-allowed": (
        "Microphone permission was denied. Allow access in the browser, then tap to speak again."
    ),
    "service-not-allowed": (
        "Microphone permission was denied. Allow access in the browser, then tap to speak again."
    ),
    "audio-capture": (
        "No microphone is available. Connect a microphone and try again, or type the question."
    ),
    "unavailable": (
        "No microphone is available. Connect a microphone and try again, or type the question."
    ),
    "no-speech": "No speech was detected. Tap to speak and try again.",
    "network": "Speech recognition lost its connection. Check the network and try again.",
}


class NormalizedQuery(TypedDict):
    query: str
    input_method: InputMethod
    language: LanguageChoice


def normalize_input_method(value: str | None) -> InputMethod:
    return "voice" if value == "voice" else "text"


def normalize_research_query(
    raw: str | None,
    input_method: str = "text",
    language: str | None = "auto",
) -> NormalizedQuery | None:
    query = (raw or "").strip()
    if len(query) < MIN_QUERY_LEN or len(query) > MAX_QUERY_LEN:
        return None
    return {
        "query": query,
        "input_method": normalize_input_method(input_method),
        "language": normalize_language_choice(language),
    }


def build_research_request(
    raw: str | None,
    input_method: str = "text",
    merchant_id: str | None = None,
    max_iterations: int = 3,
    language: str | None = "auto",
) -> dict[str, object] | None:
    """Client-side request guard. None means do not call the API."""
    normalized = normalize_research_query(raw, input_method, language)
    if normalized is None:
        return None
    body: dict[str, object] = {
        "query": normalized["query"],
        "input_method": normalized["input_method"],
        "language": normalized["language"],
        "max_iterations": max_iterations,
    }
    if merchant_id:
        body["merchant_id"] = merchant_id
    return body


def speech_ui_message(code: str) -> str:
    return SPEECH_UI_MESSAGES.get(
        code,
        "Speech recognition failed. You can type the question or tap to speak again.",
    )
