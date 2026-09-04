from __future__ import annotations

from pathlib import Path

from payops_core.config import get_settings
from payops_core.rag.chunking import chunk_document
from payops_core.rag.cleaning import clean_text
from payops_core.rag.embeddings import Embedder, get_embedder
from payops_core.rag.enrichment import enrich_chunks
from payops_core.rag.errors import IngestError
from payops_core.rag.parsing import SUPPORTED_SUFFIXES, parse_file
from payops_core.rag.types import Chunk, ParsedDocument
from payops_core.rag.vector_store import (
    InMemoryVectorStore,
    PgVectorStore,
    StoredChunk,
    VectorStore,
)


def ingest_file(path: Path) -> list[Chunk]:
    parsed = parse_file(path)
    cleaned = ParsedDocument(
        document_id=parsed.document_id,
        source=parsed.source,
        text=clean_text(parsed.text),
        metadata=parsed.metadata,
    )
    if not cleaned.text:
        raise IngestError(f"Document produced no text after cleaning: {path}")
    return enrich_chunks(chunk_document(cleaned), source_path=path)


def ingest_directory(directory: Path) -> list[Chunk]:
    if not directory.exists() or not directory.is_dir():
        raise IngestError(f"Corpus directory not found: {directory}")
    chunks: list[Chunk] = []
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not files:
        raise IngestError(f"No ingestible documents in {directory}")
    for path in files:
        chunks.extend(ingest_file(path))
    return chunks


def index_chunks(chunks: list[Chunk], store: VectorStore, embedder: Embedder | None = None) -> int:
    encoder = embedder or get_embedder()
    records = [StoredChunk(chunk=chunk, embedding=encoder.embed(chunk.text)) for chunk in chunks]
    store.upsert(records)
    return len(records)


def _default_store() -> VectorStore:
    settings = get_settings()
    if settings.vector_backend == "pgvector":
        from payops_core.data.engine import make_engine

        return PgVectorStore(make_engine(), dim=settings.embedding_dim)
    return InMemoryVectorStore()


def ingest_corpus(
    directory: Path | None = None,
    store: VectorStore | None = None,
) -> tuple[VectorStore, int]:
    settings = get_settings()
    corpus = Path(directory or settings.corpus_dir)
    target = store or _default_store()
    chunks = ingest_directory(corpus)
    count = index_chunks(chunks, target)
    return target, count


def main() -> None:
    store, count = ingest_corpus()
    print(f"Ingested {count} chunks into {type(store).__name__}.")


if __name__ == "__main__":
    main()
