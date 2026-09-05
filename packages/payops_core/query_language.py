"""Detect query language and resolve the operator's response language.

This is not a translation service and not a second retrieval pipeline.
Hindi and Hinglish reach the English corpus through ``expand_query``.
"""

from __future__ import annotations

import re
from typing import Literal

QueryLanguage = Literal["en", "hi", "hi-latn"]
LanguageChoice = Literal["auto", "en", "hi", "hi-latn"]

LANGUAGE_LABELS: dict[QueryLanguage, str] = {
    "en": "English",
    "hi": "Hindi",
    "hi-latn": "Hindi/Hinglish",
}

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN_WORD = re.compile(r"[a-z]+")

# Function words that mark romanized Hindi. "is" is English and is omitted.
_HINGLISH = frozenset(
    {
        "ka",
        "ki",
        "ke",
        "hai",
        "hain",
        "tha",
        "thi",
        "kya",
        "kyun",
        "kyon",
        "kitna",
        "kitni",
        "kitne",
        "nahi",
        "nahin",
        "matlab",
        "kyunki",
        "wala",
        "wali",
        "karo",
        "karna",
        "hoga",
        "bhugtan",
        "asafal",
    }
)
_STRONG_HINGLISH = frozenset(
    {"kitna", "kitni", "kitne", "kyun", "kyon", "matlab", "kya", "bhugtan", "asafal"}
)


def detect_query_language(text: str) -> QueryLanguage:
    if _DEVANAGARI.search(text or ""):
        return "hi"
    tokens = set(_LATIN_WORD.findall((text or "").lower()))
    hits = tokens & _HINGLISH
    if tokens & _STRONG_HINGLISH or len(hits) >= 2:
        return "hi-latn"
    return "en"


def normalize_language_choice(value: str | None) -> LanguageChoice:
    if value == "en" or value == "hi" or value == "hi-latn" or value == "auto":
        return value
    return "auto"


def resolve_response_language(text: str, choice: str | None = "auto") -> QueryLanguage:
    normalized = normalize_language_choice(choice)
    if normalized != "auto":
        return normalized
    return detect_query_language(text)


def language_label(code: str) -> str:
    if code == "en" or code == "hi" or code == "hi-latn":
        return LANGUAGE_LABELS[code]
    return LANGUAGE_LABELS["en"]


def speech_recognition_lang(choice: str | None, draft: str = "") -> str:
    resolved = resolve_response_language(draft, choice)
    return "hi-IN" if resolved in {"hi", "hi-latn"} else "en-IN"


def retrieval_query(text: str) -> str | None:
    from payops_core.rag.glossary import expand_query

    original = (text or "").strip()
    if not original:
        return None
    expanded = expand_query(original)
    return expanded if expanded != original else None
