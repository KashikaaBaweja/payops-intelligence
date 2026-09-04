# PayOps Intelligence

Autonomous investigation agent for payment operations. This repository is at **Phase 3**: document ingestion and RAG foundation.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Current scope

- Python package layout, FastAPI `/health`, config, logging, Docker
- PostgreSQL-compatible SQLAlchemy models and Alembic migrations
- Deterministic fictional seed data (no real customer information)
- Document ingestion (PDF, Markdown, TXT, JSON), chunking, embeddings, and retrieval
- Shared Pydantic investigation contracts (unused until later phases)

Agents are not implemented yet.

## Quick start

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
payops-seed
payops-ingest
PYTHONPATH=packages:. uvicorn apps.api.main:app --reload --port 8000
```

Apply migrations against Postgres, then persist chunks with pgvector:

```bash
alembic upgrade head
payops-seed
PAYOPS_VECTOR_BACKEND=pgvector payops-ingest
```

Synthetic ops docs live in `docs/corpus/`. Every chunk keeps `document_id`, source path, section, and original front matter.

## Docker

```bash
cd docker
docker compose up --build
```

Then run `alembic upgrade head` and `payops-seed` against the Compose database URL.
