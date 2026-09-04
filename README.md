# PayOps Intelligence

Autonomous investigation agent for payment operations. This repository is at **Phase 8**: evidence verification and self-correction.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Current scope

- Python package layout, FastAPI `/health`, config, logging, Docker
- PostgreSQL-compatible SQLAlchemy models and Alembic migrations
- Deterministic fictional seed data (no real customer information)
- Document ingestion (PDF, Markdown, TXT, JSON), chunking, embeddings, and retrieval
- Researcher, Data Analyst, and Webhook Inspector tools
- LangGraph orchestration: plan → investigate → aggregate → sufficiency → (retry or verify/write/critic)
- Verifier checks claims against evidence (unsupported, contradictory, missing, weak) and can request another investigation pass
- Critic reviews the draft report; the Writer cannot override verifier findings
- Safe execution traces (node, action, tool, query, evidence IDs, decision, verification) — no private chain-of-thought

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
