from __future__ import annotations

from payops_core.config import get_settings
from payops_core.models.schemas import RetrievalHit
from payops_core.rag.embeddings import Embedder, get_embedder
from payops_core.rag.vector_store import VectorStore


class DocumentRetriever:
    """Vector retriever. Returns structured evidence hits, not free text."""

    def __init__(self, store: VectorStore, embedder: Embedder | None = None) -> None:
        self.store = store
        self.embedder = embedder or get_embedder()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> list[RetrievalHit]:
        if not query.strip() or top_k <= 0:
            return []
        filters = {"doc_type": doc_type} if doc_type else None
        embedding = self.embedder.embed(query)
        return self.store.search(embedding, top_k=top_k, filters=filters)


def search_docs(
    query: str,
    top_k: int = 5,
    doc_type_filter: str | None = None,
    retriever: DocumentRetriever | None = None,
) -> list[RetrievalHit]:
    """Public retrieval interface. Agents are not wired yet; this is the RAG seam."""

    active = retriever or build_retriever()
    return active.retrieve(query, top_k=top_k, doc_type=doc_type_filter)


def build_retriever(store: VectorStore | None = None) -> DocumentRetriever:
    settings = get_settings()
    if store is not None:
        return DocumentRetriever(store)
    if settings.vector_backend == "pgvector":
        from payops_core.data.engine import make_engine
        from payops_core.rag.vector_store import PgVectorStore

        return DocumentRetriever(PgVectorStore(make_engine(), dim=settings.embedding_dim))
    from payops_core.rag.vector_store import InMemoryVectorStore

    return DocumentRetriever(InMemoryVectorStore())
