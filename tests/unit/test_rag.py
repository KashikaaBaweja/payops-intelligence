from pathlib import Path

from payops_core.rag.pipeline import chunk_document
from payops_core.rag.vector_store import build_store


def test_chunker_keeps_doc_metadata():
    path = Path("docs/corpus/error-codes.md")
    chunks = chunk_document(path)
    assert chunks
    assert chunks[0].doc_id == "error-codes"
    assert chunks[0].metadata["doc_type"] == "error_codes"


def test_lexical_search_finds_gateway_timeout():
    store = build_store(Path("docs/corpus"))
    hits = store.search("UPI GATEWAY_TIMEOUT processor incident", top_k=3)
    assert hits
    joined = " ".join(chunk.text.lower() for chunk, _ in hits)
    assert "gateway_timeout" in joined or "gateway timeout" in joined
