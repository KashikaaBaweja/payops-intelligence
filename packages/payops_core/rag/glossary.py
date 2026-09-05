"""English/Hindi/Hinglish payment-term expansion. This is not multilingual embeddings."""

from __future__ import annotations

import re

GLOSSARY: tuple[tuple[str, str], ...] = (
    ("भुगतान", "payment"),
    ("असफल", "failed failure"),
    ("विफल", "failed failure"),
    ("सफलता", "success"),
    ("सफल", "success succeeded"),
    ("वेबहुक", "webhook"),
    ("वापसी", "refund"),
    ("समय समाप्त", "timeout GATEWAY_TIMEOUT"),
    ("टाइमआउट", "timeout GATEWAY_TIMEOUT"),
    ("व्यापारी", "merchant"),
    ("मतलब", "meaning"),
    ("क्यों", "why"),
    ("दर", "rate"),
    ("स्वास्थ्य", "health"),
    ("जोखिम", "risk"),
    ("bhugtan", "payment"),
    ("asafal", "failed failure"),
    ("vyapari", "merchant"),
    ("matlab", "meaning"),
    ("kyun", "why"),
    ("kyon", "why"),
    ("kya", "what meaning"),
    ("kitna", "how much"),
    ("kitni", "how much"),
    ("kitne", "how much"),
    ("jochim", "risk"),
    ("len-den", "transaction payment"),
)


def _term_present(term: str, text: str, lowered: str) -> bool:
    if any("\u0900" <= char <= "\u097f" for char in term):
        return term in text
    return re.search(rf"\b{re.escape(term.lower())}\b", lowered) is not None


def expand_query(text: str) -> str:
    extras: list[str] = []
    lowered = text.lower()
    for term, english in GLOSSARY:
        if _term_present(term, text, lowered):
            extras.extend(english.split())
    if not extras:
        return text
    unique = list(dict.fromkeys(extras))
    return f"{text} {' '.join(unique)}"
