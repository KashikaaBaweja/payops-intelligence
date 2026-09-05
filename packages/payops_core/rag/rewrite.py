"""Rewrite a retrieval query from missing facets. Not free-form generation."""

from __future__ import annotations

from payops_core.models.schemas import QueryAnalysis, SearchQuery
from payops_core.rag.analysis import TOPIC_HINTS
from payops_core.rag.glossary import expand_query


def rewrite_query(
    analysis: QueryAnalysis,
    current: SearchQuery,
    *,
    missing_facets: list[str],
    used: set[tuple[str, str | None]],
    seed_queries: list[SearchQuery],
    no_results: bool,
) -> SearchQuery | None:
    for seed in seed_queries:
        if _unused(seed, used):
            return seed.model_copy(update={"rationale": seed.rationale or "unused seed query"})
    candidates: list[SearchQuery] = []
    for facet in missing_facets:
        if facet in analysis.error_codes:
            candidates.append(
                SearchQuery(
                    query=f"{facet} processor incident",
                    doc_type="error_codes",
                    rationale=f"cover missing error-code facet {facet}",
                )
            )
            candidates.append(
                SearchQuery(
                    query=f"{facet} runbook timeout failure",
                    doc_type="runbook",
                    rationale=f"runbook rewrite for {facet}",
                )
            )
        for needles, extra_query, doc_type, topic in TOPIC_HINTS:
            if facet == topic or facet in needles:
                candidates.append(
                    SearchQuery(
                        query=extra_query,
                        doc_type=doc_type,
                        rationale=f"cover missing topic {topic}",
                    )
                )
    if no_results:
        expanded = expand_query(analysis.question)
        candidates.append(
            SearchQuery(
                query=expanded,
                doc_type=None,
                rationale="broaden after empty retrieval",
            )
        )
        if current.doc_type:
            candidates.append(
                SearchQuery(
                    query=current.query,
                    doc_type=None,
                    rationale="retry without doc_type filter",
                )
            )
    if not candidates and current.query != analysis.question:
        candidates.append(
            SearchQuery(
                query=analysis.question,
                doc_type=None,
                rationale="fall back to original question",
            )
        )
    for candidate in candidates:
        if _unused(candidate, used):
            return candidate
    return None


def _unused(query: SearchQuery, used: set[tuple[str, str | None]]) -> bool:
    return (query.query.lower(), query.doc_type) not in used
