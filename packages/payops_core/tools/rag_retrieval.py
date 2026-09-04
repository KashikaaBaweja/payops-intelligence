from payops_core.models import EvidenceItem
from payops_core.rag.vector_store import get_store


def search_docs(query: str, doc_type: str | None = None, top_k: int = 5) -> list[EvidenceItem]:
    store = get_store()
    hits = store.search(query, doc_type=doc_type, top_k=top_k)
    items: list[EvidenceItem] = []
    for index, (chunk, score) in enumerate(hits):
        items.append(
            EvidenceItem(
                evidence_id=f"doc-{chunk.chunk_id}",
                source="doc",
                doc_id=chunk.doc_id,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                score=score,
                text_snippet=chunk.text[:500],
                metadata=chunk.metadata,
            )
        )
        _ = index
    return items
