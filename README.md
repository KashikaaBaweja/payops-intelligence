# PayOps Intelligence

Autonomous investigation agent for payment operations. This repository is at **Phase 2**: synthetic payment-platform data model.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Current scope

- Python package layout, FastAPI `/health`, config, logging, Docker
- PostgreSQL-compatible SQLAlchemy models
- Alembic migrations
- Deterministic fictional seed data (no real customer information)
- Shared Pydantic investigation contracts (unused until later phases)

Agents and RAG are not implemented yet.

## Quick start

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
payops-seed
PYTHONPATH=packages:. uvicorn apps.api.main:app --reload --port 8000
```

Apply migrations against Postgres:

```bash
alembic upgrade head
payops-seed
```

## Docker

```bash
cd docker
docker compose up --build
```

Then run `alembic upgrade head` and `payops-seed` against the Compose database URL.
