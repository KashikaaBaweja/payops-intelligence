from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine

from payops_core.models.schemas import RetrievalHit
from payops_core.rag.embeddings import cosine
from payops_core.rag.types import Chunk


@dataclass
class StoredChunk:
    chunk: Chunk
    embedding: list[float]


class VectorStore(Protocol):
    def upsert(self, records: list[StoredChunk]) -> None: ...

    def count(self) -> int: ...

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]: ...


class InMemoryVectorStore:
    """Local store used for tests and sqlite/dev when Postgres is not available."""

    def __init__(self) -> None:
        self._records: list[StoredChunk] = []

    def upsert(self, records: list[StoredChunk]) -> None:
        existing = {item.chunk.chunk_id: item for item in self._records}
        for record in records:
            existing[record.chunk.chunk_id] = record
        self._records = list(existing.values())

    def count(self) -> int:
        return len(self._records)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        scored: list[RetrievalHit] = []
        for record in self._records:
            if not _matches(record.chunk.metadata, filters):
                continue
            score = cosine(query_embedding, record.embedding)
            if score <= 0:
                continue
            scored.append(_to_hit(record.chunk, score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


class PgVectorStore:
    """Postgres + pgvector backend. Requires `CREATE EXTENSION vector`."""

    def __init__(self, engine: Engine, dim: int = 128) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("PgVectorStore requires a PostgreSQL engine")
        self.engine = engine
        self.dim = dim
        self.ensure_schema()

    def ensure_schema(self) -> None:
        ddl = f"""
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id VARCHAR(64) PRIMARY KEY,
                document_id VARCHAR(64) NOT NULL,
                source TEXT NOT NULL,
                section TEXT NOT NULL,
                body TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({self.dim}) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id
                ON document_chunks (document_id);
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

    def upsert(self, records: list[StoredChunk]) -> None:
        sql = """
            INSERT INTO document_chunks
                (chunk_id, document_id, source, section, body, metadata, embedding)
            VALUES
                (:chunk_id, :document_id, :source, :section, :body,
                 CAST(:metadata AS jsonb), CAST(:embedding AS vector))
            ON CONFLICT (chunk_id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                source = EXCLUDED.source,
                section = EXCLUDED.section,
                body = EXCLUDED.body,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
        """
        with self.engine.begin() as conn:
            for record in records:
                conn.execute(
                    text(sql),
                    {
                        "chunk_id": record.chunk.chunk_id,
                        "document_id": record.chunk.document_id,
                        "source": record.chunk.source,
                        "section": record.chunk.section,
                        "body": record.chunk.text,
                        "metadata": json.dumps(record.chunk.metadata),
                        "embedding": _vector_literal(record.embedding),
                    },
                )

    def count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar() or 0)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        fetch_k = max(top_k, top_k * 8) if filters else top_k
        sql = """
            SELECT chunk_id, document_id, source, section, body, metadata,
                   1 - (embedding <=> CAST(:query AS vector)) AS score
            FROM document_chunks
            ORDER BY embedding <=> CAST(:query AS vector)
            LIMIT :top_k
        """
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(sql),
                {"query": _vector_literal(query_embedding), "top_k": fetch_k},
            ).mappings()
            hits: list[RetrievalHit] = []
            for row in rows:
                raw_meta = row["metadata"]
                metadata = raw_meta if isinstance(raw_meta, dict) else json.loads(raw_meta)
                if not _matches(metadata, filters):
                    continue
                hits.append(
                    RetrievalHit(
                        document_id=row["document_id"],
                        chunk_id=row["chunk_id"],
                        source=row["source"],
                        section=row["section"],
                        text=row["body"],
                        score=float(row["score"] or 0),
                        metadata=metadata,
                    )
                )
                if len(hits) >= top_k:
                    break
            return hits


def _matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())


def _to_hit(chunk: Chunk, score: float) -> RetrievalHit:
    return RetrievalHit(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        source=chunk.source,
        section=chunk.section,
        text=chunk.text,
        score=score,
        metadata=chunk.metadata,
    )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"
