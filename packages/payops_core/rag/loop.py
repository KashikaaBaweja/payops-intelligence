"""Bounded agentic retrieval loop. Evidence in, citations out — no chain-of-thought."""

from __future__ import annotations

import time
from collections.abc import Callable
from logging import getLogger
from typing import Literal

from payops_core.models.schemas import (
    AgenticRagResult,
    EvidenceBundle,
    EvidenceItem,
    QueryAnalysis,
    RetrievalHit,
    RetrievalRound,
    SearchQuery,
    SourceCitation,
)
from payops_core.rag.analysis import ERROR_CODES, OPPOSITE_CODES, analyze_query, codes_in
from payops_core.rag.relevance import relevance_score, rerank
from payops_core.rag.rewrite import rewrite_query

logger = getLogger(__name__)

RetrieveFn = Callable[[str, str | None], list[RetrievalHit]]


def run_agentic_rag(
    question: str,
    *,
    retrieve: RetrieveFn,
    seed_queries: list[SearchQuery] | None = None,
    analysis: QueryAnalysis | None = None,
    min_score: float = 0.05,
    min_kept: int = 1,
    max_iterations: int = 3,
) -> AgenticRagResult:
    started = time.perf_counter()
    parsed = analysis or analyze_query(question)
    seeds = list(seed_queries or [])
    if not seeds and question.strip():
        seeds = [SearchQuery(query=question.strip(), rationale="original research question")]
    if not seeds:
        return AgenticRagResult(
            question=question,
            analysis=parsed,
            max_iterations=max_iterations,
            grounded_excerpt="No document evidence met the relevance threshold.",
        )

    used: set[tuple[str, str | None]] = set()
    current = seeds[0]
    kept: dict[str, EvidenceItem] = {}
    rejected = 0
    rounds: list[RetrievalRound] = []
    tried: list[SearchQuery] = []

    for index in range(1, max(1, max_iterations) + 1):
        used.add((current.query.lower(), current.doc_type))
        tried.append(current)
        t0 = time.perf_counter()
        hits = retrieve(current.query, current.doc_type)
        scored: list[tuple[RetrievalHit, float, list[str]]] = []
        round_rejected = 0
        for hit in hits:
            score, keep, _reasons = relevance_score(parsed, current, hit, min_score=min_score)
            if not keep:
                round_rejected += 1
                rejected += 1
                continue
            scored.append((hit, score, _reasons))
        ranked = rerank(scored)
        round_ids: list[str] = []
        for hit, score, reasons in ranked:
            item = _to_evidence(hit, current, score, reasons, index)
            previous = kept.get(item.evidence_id)
            if previous is None or (item.score or 0) > (previous.score or 0):
                kept[item.evidence_id] = item
            round_ids.append(item.evidence_id)
        missing = _missing_facets(parsed, kept)
        sufficient = _docs_sufficient(kept, missing, min_kept=min_kept)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        decision: Literal["sufficient", "rewrite", "exhausted", "no_results"]
        if sufficient:
            decision = "sufficient"
        elif index >= max_iterations:
            decision = "no_results" if not hits else "exhausted"
        else:
            decision = "rewrite"
        previous_query = tried[-2].query if len(tried) > 1 else None
        rewrite_reason = current.rationale if previous_query else None
        rounds.append(
            RetrievalRound(
                search_index=index,
                query=current.query,
                rewritten_from=previous_query,
                rewrite_reason=rewrite_reason,
                retrieved=len(hits),
                kept=len(ranked),
                rejected=round_rejected,
                sufficient=sufficient,
                decision=decision,
                latency_ms=latency_ms,
                evidence_ids=round_ids,
                missing_facets=missing,
            )
        )
        logger.info(
            "rag_search index=%s decision=%s query=%s retrieved=%s kept=%s "
            "missing=%s latency_ms=%s",
            index,
            decision,
            current.query,
            len(hits),
            len(ranked),
            ",".join(missing) or "none",
            latency_ms,
        )
        if sufficient or index >= max_iterations:
            break
        nxt = rewrite_query(
            parsed,
            current,
            missing_facets=missing,
            used=used,
            seed_queries=seeds,
            no_results=not hits or not ranked,
        )
        if nxt is None:
            rounds[-1] = rounds[-1].model_copy(update={"decision": "exhausted"})
            break
        current = nxt

    items = sorted(kept.values(), key=lambda item: item.score or 0, reverse=True)
    conflicting, conflict_note = _conflicts(items)
    citations = [
        SourceCitation(
            evidence_id=item.evidence_id,
            document_id=item.doc_id or "",
            section=item.section or "",
            score=float(item.score or 0),
        )
        for item in items
    ]
    excerpt = _grounded_excerpt(items, conflicting, conflict_note)
    known = {item.evidence_id for item in items}
    verified = bool(citations) and all(item.evidence_id in known for item in citations)
    sufficient = bool(rounds and rounds[-1].sufficient and verified)
    if conflicting:
        sufficient = False
    return AgenticRagResult(
        question=question,
        analysis=parsed,
        rounds=rounds,
        iterations=len(rounds),
        max_iterations=max_iterations,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        sufficient=sufficient,
        conflicting=conflicting,
        conflict_note=conflict_note,
        queries=tried,
        evidence=EvidenceBundle(items=items),
        citations=citations,
        grounded_excerpt=excerpt,
        rejected_count=rejected,
        sources_verified=verified,
    )


def _to_evidence(
    hit: RetrievalHit,
    query: SearchQuery,
    score: float,
    reasons: list[str],
    search_index: int,
) -> EvidenceItem:
    item = hit.to_evidence()
    metadata = {
        **item.metadata,
        "source": hit.source,
        "document_id": hit.document_id,
        "section": hit.section,
        "query": query.query,
        "relevance": score,
        "rank_reasons": reasons,
        "search_index": search_index,
    }
    if query.doc_type:
        metadata.setdefault("doc_type_filter", query.doc_type)
    return item.model_copy(update={"score": score, "metadata": metadata})


def _missing_facets(analysis: QueryAnalysis, kept: dict[str, EvidenceItem]) -> list[str]:
    if not analysis.facets:
        return []
    blob = " ".join(item.text_snippet for item in kept.values()).upper()
    missing: list[str] = []
    for code in analysis.error_codes:
        if code not in blob:
            missing.append(code)
    lower = blob.lower()
    for topic in analysis.topics:
        if topic not in lower:
            missing.append(topic)
    return missing


def _docs_sufficient(
    kept: dict[str, EvidenceItem],
    missing: list[str],
    *,
    min_kept: int,
) -> bool:
    if len(kept) < min_kept:
        return False
    if missing:
        return False
    return True


def _conflicts(items: list[EvidenceItem]) -> tuple[bool, str | None]:
    primaries: list[tuple[str | None, str | None, str]] = []
    for item in items:
        code = _primary_code(item)
        if code:
            primaries.append((item.doc_id, item.section, code))
    for index, (doc_id, section, code) in enumerate(primaries):
        for other_doc, other_section, other in primaries[index + 1 :]:
            if other == code or other not in OPPOSITE_CODES.get(code, frozenset()):
                continue
            if doc_id != other_doc or section != other_section:
                return True, f"{code} vs {other}"
    return False, None


def _primary_code(item: EvidenceItem) -> str | None:
    section = (item.section or "").upper().replace(" ", "_")
    if section in ERROR_CODES:
        return section
    found = codes_in(item.text_snippet)
    if len(found) == 1:
        return next(iter(found))
    return None


def _grounded_excerpt(
    items: list[EvidenceItem],
    conflicting: bool,
    conflict_note: str | None,
) -> str:
    if not items:
        return "No document evidence met the relevance threshold."
    parts = [
        f"{item.section or item.doc_id}: {item.text_snippet[:180]} [{item.evidence_id}]"
        for item in items[:3]
    ]
    text = " ".join(parts)
    if conflicting and conflict_note:
        return f"{text} Conflicting sources remain unresolved ({conflict_note})."
    return text
