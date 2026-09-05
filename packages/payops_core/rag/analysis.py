"""Deterministic query analysis for agentic retrieval. No LLM."""

from __future__ import annotations

import re

from payops_core.models.schemas import QueryAnalysis
from payops_core.rag.glossary import expand_query

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "does",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "why",
    "with",
}
ERROR_CODES = (
    "GATEWAY_TIMEOUT",
    "INSUFFICIENT_FUNDS",
    "DO_NOT_HONOR",
    "AUTHENTICATION_FAILED",
    "WEBHOOK_TIMEOUT",
)
TOPIC_HINTS: tuple[tuple[frozenset[str], str, str | None, str], ...] = (
    (
        frozenset({"webhook", "webhooks", "ack"}),
        "webhook delayed delivery ACK payment.succeeded",
        "webhook_docs",
        "webhook",
    ),
    (
        frozenset({"refund", "refunds"}),
        "refund policy succeeded payment",
        "refund_policy",
        "refund",
    ),
    (
        frozenset({"dispute", "disputes", "chargeback"}),
        "payment disputes risk signal",
        "api_docs",
        "dispute",
    ),
    (
        frozenset({"settlement", "settlements"}),
        "settlement batch succeeded payments",
        None,
        "settlement",
    ),
    (
        frozenset({"runbook", "incident"}),
        "incident runbook sparse merchant evidence",
        "runbook",
        "runbook",
    ),
    (
        frozenset({"lifecycle", "status"}),
        "payment lifecycle succeeded pending failed",
        None,
        "lifecycle",
    ),
    (
        frozenset({"gateway_timeout", "upi", "failure", "failed", "timeout"}),
        "GATEWAY_TIMEOUT UPI processor timeout",
        "runbook",
        "timeout",
    ),
)
OPPOSITE_CODES: dict[str, frozenset[str]] = {
    "GATEWAY_TIMEOUT": frozenset({"INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "AUTHENTICATION_FAILED"}),
    "INSUFFICIENT_FUNDS": frozenset({"GATEWAY_TIMEOUT"}),
    "DO_NOT_HONOR": frozenset({"GATEWAY_TIMEOUT"}),
    "AUTHENTICATION_FAILED": frozenset({"GATEWAY_TIMEOUT"}),
    "WEBHOOK_TIMEOUT": frozenset({"GATEWAY_TIMEOUT"}),
}


def analyze_query(question: str) -> QueryAnalysis:
    expanded = expand_query(question)
    tokens = sorted(tokens_of(expanded))
    compact = expanded.upper().replace("-", "_")
    codes = [code for code in ERROR_CODES if code in compact]
    topics: list[str] = []
    for needles, _query, _doc_type, topic in TOPIC_HINTS:
        if set(tokens) & needles and topic not in topics:
            topics.append(topic)
    facets = [*codes, *topics]
    return QueryAnalysis(
        question=question,
        facets=facets,
        error_codes=codes,
        topics=topics,
        tokens=tokens,
    )


def tokens_of(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def codes_in(text: str) -> set[str]:
    compact = text.upper().replace("-", "_").replace(" ", "_")
    return {code for code in ERROR_CODES if code in compact}
