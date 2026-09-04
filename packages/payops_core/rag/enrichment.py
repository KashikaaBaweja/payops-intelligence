from __future__ import annotations

from pathlib import Path

from payops_core.rag.types import Chunk


def enrich_chunks(chunks: list[Chunk], source_path: Path | None = None) -> list[Chunk]:
    """Attach source/path metadata to every chunk without dropping existing fields."""

    enriched: list[Chunk] = []
    for index, chunk in enumerate(chunks):
        metadata = {
            **chunk.metadata,
            "chunk_index": index,
            "document_id": chunk.document_id,
            "source": chunk.source,
            "section": chunk.section,
        }
        if source_path is not None:
            metadata.setdefault("source_path", str(source_path))
            metadata.setdefault("filename", source_path.name)
        enriched.append(
            Chunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source=chunk.source,
                section=chunk.section,
                text=chunk.text,
                metadata=metadata,
            )
        )
    return enriched
