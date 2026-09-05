from __future__ import annotations

from payops_core.agents.retrieval import RetrievalAgent
from payops_core.models.schemas import (
    EvidenceBundle,
    EvidenceItem,
    ResearcherResult,
    RetrievalHit,
    SearchQuery,
    Task,
)
from payops_core.rag.analysis import ERROR_CODES, TOPIC_HINTS, analyze_query, tokens_of
from payops_core.rag.glossary import expand_query
from payops_core.rag.loop import run_agentic_rag
from payops_core.rag.retriever import DocumentRetriever


class ResearcherAgent:
    """Run the agentic RAG loop. Does not write a final investigation answer."""

    def __init__(
        self,
        retriever: DocumentRetriever,
        top_k: int = 5,
        min_score: float = 0.05,
        max_iterations: int = 3,
    ) -> None:
        self.retriever = retriever
        self.retrieval = RetrievalAgent(retriever, top_k=top_k)
        self.top_k = top_k
        self.min_score = min_score
        self.max_iterations = max_iterations

    def research(self, question: str, task: Task | None = None) -> ResearcherResult:
        if task is not None and task.task_type != "retrieve_docs":
            raise ValueError("ResearcherAgent only executes retrieve_docs tasks")
        queries = self.formulate_queries(question, task)
        if not queries:
            return ResearcherResult(question=question, queries=[], evidence=EvidenceBundle())
        rag = run_agentic_rag(
            question,
            retrieve=self.retrieval.retrieve,
            seed_queries=queries,
            analysis=analyze_query(question),
            min_score=self.min_score,
            max_iterations=self.max_iterations,
        )
        return ResearcherResult(
            question=question,
            queries=queries,
            evidence=rag.evidence,
            rejected_count=rag.rejected_count,
            rag=rag,
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

        expanded = expand_query(question)
        compact = expanded.upper().replace("-", "_")
        tokens = tokens_of(expanded)

        # Specific catalog / topic queries first. The agentic loop stops as soon as
        # kept evidence covers the detected topics, so an unfiltered first search
        # can keep a lexical neighbor (refunds-faq, error-codes) and never run the
        # refund_policy / runbook / webhook_docs filter.
        for code in ERROR_CODES:
            if code in compact:
                add(code, "error_codes", f"error-code catalog for {code}")
                add(f"{code} processor incident", "runbook", f"failure runbook for {code}")

        matched: list[tuple[str | None, str, str]] = []
        for needles, extra_query, doc_type, topic in TOPIC_HINTS:
            if tokens & needles:
                matched.append((doc_type, extra_query, topic))
                add(extra_query, doc_type, topic)

        inferred = matched[0][0] if len(matched) == 1 else None
        if task is not None and task.query:
            add(task.query, inferred, "planner-provided retrieve_docs query")
        add(question, inferred, "original research question")
        if expanded != question:
            add(expanded, inferred, "glossary-expanded research question")
        return queries

    def _is_relevant(self, question: str, query: SearchQuery, hit: RetrievalHit) -> bool:
        from payops_core.rag.relevance import relevance_score

        _score, keep, _reasons = relevance_score(
            analyze_query(question),
            query,
            hit,
            min_score=self.min_score,
        )
        return keep

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
