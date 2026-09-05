"""Score and rank retrieved chunks. Deterministic — not an LLM reranker."""

from __future__ import annotations

from payops_core.models.schemas import QueryAnalysis, RetrievalHit, SearchQuery
from payops_core.rag.analysis import codes_in, tokens_of
from payops_core.rag.glossary import expand_query


def relevance_score(
    analysis: QueryAnalysis,
    query: SearchQuery,
    hit: RetrievalHit,
    min_score: float = 0.05,
) -> tuple[float, bool, list[str]]:
    reasons: list[str] = []
    if hit.score < min_score:
        return 0.0, False, ["below_vector_floor"]
    focus = (
        set(analysis.tokens) | tokens_of(expand_query(analysis.question)) | tokens_of(query.query)
    )
    blob = " ".join(part for part in (hit.text, hit.section, hit.document_id, hit.source) if part)
    hit_tokens = tokens_of(blob)
    overlap = focus & hit_tokens
    if not overlap:
        return round(float(hit.score), 4), False, ["no_token_overlap"]
    coverage = len(overlap) / max(len(focus), 1)
    score = min(1.0, 0.55 * float(hit.score) + 0.45 * coverage)
    reasons.append("token_overlap")
    shared_codes = set(analysis.error_codes) & codes_in(blob)
    if shared_codes:
        score = min(1.0, score + 0.15)
        reasons.append("error_code_match")
    shared_topics = [topic for topic in analysis.topics if topic in blob.lower()]
    if shared_topics:
        score = min(1.0, score + 0.08)
        reasons.append("topic_match")
    return round(score, 4), True, reasons


def rerank(
    scored: list[tuple[RetrievalHit, float, list[str]]],
) -> list[tuple[RetrievalHit, float, list[str]]]:
    return sorted(scored, key=lambda item: (item[1], item[0].score), reverse=True)
