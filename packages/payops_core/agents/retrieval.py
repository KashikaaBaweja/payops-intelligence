from __future__ import annotations

from payops_core.models.schemas import RetrievalHit
from payops_core.rag.retriever import DocumentRetriever, search_docs


class RetrievalAgent:
    """Execute document retrieval only. Does not formulate queries or write reports."""

    def __init__(self, retriever: DocumentRetriever, top_k: int = 5) -> None:
        self.retriever = retriever
        self.top_k = top_k

    def retrieve(self, query: str, doc_type: str | None = None) -> list[RetrievalHit]:
        if not query.strip():
            return []
        return search_docs(
            query,
            top_k=self.top_k,
            doc_type_filter=doc_type,
            retriever=self.retriever,
        )
