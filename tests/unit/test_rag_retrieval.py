from pathlib import Path

import pytest
from payops_core.data.engine import make_engine
from payops_core.rag.ingest import index_chunks, ingest_corpus, ingest_file
from payops_core.rag.retriever import DocumentRetriever, search_docs
from payops_core.rag.vector_store import InMemoryVectorStore, PgVectorStore

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"


def _retriever() -> DocumentRetriever:
    store, _count = ingest_corpus(CORPUS, store=InMemoryVectorStore())
    return DocumentRetriever(store)


def test_retrieval_returns_structured_evidence() -> None:
    hits = search_docs(
        "UPI GATEWAY_TIMEOUT Harbor Retail processor incident",
        top_k=5,
        retriever=_retriever(),
    )
    assert hits
    top = hits[0]
    assert top.document_id
    assert top.chunk_id
    assert top.source
    assert top.section
    assert top.text
    assert top.score > 0
    assert isinstance(top.metadata, dict)
    assert "document_id" in top.metadata
    assert "source" in top.metadata
    combined = " ".join(hit.text for hit in hits)
    assert "GATEWAY_TIMEOUT" in combined
    evidence = top.to_evidence()
    assert evidence.source == "doc"
    assert evidence.doc_id == top.document_id
    assert evidence.chunk_id == top.chunk_id


def test_retrieval_can_filter_by_doc_type() -> None:
    retriever = _retriever()
    hits = search_docs(
        "delayed webhook ACK payment.succeeded",
        top_k=5,
        doc_type_filter="webhook_docs",
        retriever=retriever,
    )
    assert hits
    assert all(hit.metadata.get("doc_type") == "webhook_docs" for hit in hits)


def test_empty_results() -> None:
    retriever = _retriever()
    assert retriever.retrieve("   ") == []
    assert search_docs("query", top_k=0, retriever=retriever) == []
    empty = DocumentRetriever(InMemoryVectorStore())
    assert empty.retrieve("GATEWAY_TIMEOUT") == []


def test_ingest_indexes_chunks_for_later_retrieval(tmp_path: Path) -> None:
    source = CORPUS / "webhooks.md"
    chunks = ingest_file(source)
    store = InMemoryVectorStore()
    indexed = index_chunks(chunks, store)
    assert indexed == len(chunks)
    hits = DocumentRetriever(store).retrieve("webhook delayed ACK Cedar Digital Goods")
    assert hits
    assert all(hit.document_id == "webhook-docs" for hit in hits)


def test_pgvector_store_requires_postgres() -> None:
    engine = make_engine("sqlite://")
    with pytest.raises(ValueError, match="PostgreSQL"):
        PgVectorStore(engine)
