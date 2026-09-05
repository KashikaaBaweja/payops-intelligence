"""English/Hindi payment-term expansion. This is not multilingual embeddings."""

from __future__ import annotations

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
)


def expand_query(text: str) -> str:
    extras: list[str] = []
    lowered = text.lower()
    for term, english in GLOSSARY:
        if term in text or term.lower() in lowered:
            extras.extend(english.split())
    if not extras:
        return text
    unique = list(dict.fromkeys(extras))
    return f"{text} {' '.join(unique)}"
