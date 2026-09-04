from __future__ import annotations

import re

from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceItem,
    ResearcherResult,
    RetrievalHit,
    SearchQuery,
    Task,
)
from payops_core.rag.retriever import DocumentRetriever, search_docs

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
_ERROR_CODES = (
    "GATEWAY_TIMEOUT",
    "INSUFFICIENT_FUNDS",
    "DO_NOT_HONOR",
    "AUTHENTICATION_FAILED",
    "WEBHOOK_TIMEOUT",
)
_TOPIC_HINTS: tuple[tuple[frozenset[str], str, str | None, str], ...] = (
    (
        frozenset({"webhook", "webhooks", "ack"}),
        "webhook delayed delivery ACK payment.succeeded",
        "webhook_docs",
        "webhook delivery docs",
    ),
    (
        frozenset({"refund", "refunds"}),
        "refund policy succeeded payment",
        "refund_policy",
        "refund policy",
    ),
    (
        frozenset({"dispute", "disputes", "chargeback"}),
        "payment disputes risk signal",
        "api_docs",
        "disputes guide",
    ),
    (
        frozenset({"settlement", "settlements"}),
        "settlement batch succeeded payments",
        None,
        "settlement docs",
    ),
    (
        frozenset({"runbook", "incident"}),
        "incident runbook sparse merchant evidence",
        "runbook",
        "incident runbook",
    ),
    (
        frozenset({"gateway_timeout", "upi", "failure", "failed", "timeout"}),
        "GATEWAY_TIMEOUT UPI processor timeout",
        "runbook",
        "payment failure runbook",
    ),
)


class ResearcherAgent:
    """Retrieve and score document evidence. Does not write a final answer."""

    def __init__(
        self,
        retriever: DocumentRetriever,
        top_k: int = 5,
        min_score: float = 0.05,
    ) -> None:
        self.retriever = retriever
        self.top_k = top_k
        self.min_score = min_score

    def research(self, question: str, task: Task | None = None) -> ResearcherResult:
        if task is not None and task.task_type != "retrieve_docs":
            raise ValueError("ResearcherAgent only executes retrieve_docs tasks")
        queries = self.formulate_queries(question, task)
        if not queries:
            return ResearcherResult(question=question, queries=[], evidence=EvidenceBundle())

        kept: dict[str, EvidenceItem] = {}
        rejected = 0
        for query in queries:
            for hit in search_docs(
                query.query,
                top_k=self.top_k,
                doc_type_filter=query.doc_type,
                retriever=self.retriever,
            ):
                if not self._is_relevant(question, query, hit):
                    rejected += 1
                    continue
                item = self._to_evidence(hit, query)
                previous = kept.get(item.evidence_id)
                if previous is None or (item.score or 0) > (previous.score or 0):
                    kept[item.evidence_id] = item

        items = sorted(kept.values(), key=lambda item: item.score or 0, reverse=True)
        return ResearcherResult(
            question=question,
            queries=queries,
            evidence=EvidenceBundle(items=items),
            rejected_count=rejected,
        )

    def formulate_queries(self, question: str, task: Task | None = None) -> list[SearchQuery]:
        queries: list[SearchQuery] = []
        seen: set[tuple[str, str | None]] = set()

        def add(text: str, doc_type: str | None, rationale: str) -> None:
            cleaned = " ".join(text.split())
            key = (cleaned.lower(), doc_type)
            if not cleaned or key in seen:
                return
            seen.add(key)
            queries.append(SearchQuery(query=cleaned, doc_type=doc_type, rationale=rationale))

        if task is not None and task.query:
            add(task.query, None, "planner-provided retrieve_docs query")
        add(question, None, "original research question")

        compact = question.upper().replace("-", "_")
        for code in _ERROR_CODES:
            if code in compact:
                add(code, "error_codes", f"error-code catalog for {code}")
                add(f"{code} processor incident", "runbook", f"failure runbook for {code}")

        tokens = _tokens(question)
        for needles, extra_query, doc_type, rationale in _TOPIC_HINTS:
            if tokens & needles:
                add(extra_query, doc_type, rationale)
        return queries

    def _is_relevant(self, question: str, query: SearchQuery, hit: RetrievalHit) -> bool:
        if hit.score < self.min_score:
            return False
        focus = _tokens(question) | _tokens(query.query)
        blob = " ".join(
            part for part in (hit.text, hit.section, hit.document_id, hit.source) if part
        )
        return bool(focus & _tokens(blob))

    def _to_evidence(self, hit: RetrievalHit, query: SearchQuery) -> EvidenceItem:
        item = hit.to_evidence()
        metadata = {
            **item.metadata,
            "source": hit.source,
            "document_id": hit.document_id,
            "section": hit.section,
            "query": query.query,
        }
        if query.doc_type:
            metadata.setdefault("doc_type_filter", query.doc_type)
        return item.model_copy(update={"metadata": metadata})


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }
