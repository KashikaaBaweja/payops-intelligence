# ADR-003: Deterministic embeddings behind a store-agnostic retriever

Status: accepted

## Decision
MVP retrieval uses a hashing embedder (no API key) behind `DocumentRetriever` / `search_docs`. Storage is a `VectorStore` protocol: in-memory for tests and local sqlite, pgvector when `PAYOPS_VECTOR_BACKEND=pgvector`.

## Why
A local demo must run without embedding API keys. Hashing vectors keep tests deterministic while preserving the same chunk metadata and cosine-search interface that Postgres/pgvector will use in production.
