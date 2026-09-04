# PayOps Intelligence

Autonomous investigation agent for payment operations. This repository is at **Phase 13**: production engineering hardening.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Current scope

- Python package layout, FastAPI `/health` and `/health/ready`, config, logging, Docker
- PostgreSQL-compatible SQLAlchemy models and Alembic migrations
- Deterministic fictional seed data (no real customer information)
- Document ingestion (PDF, Markdown, TXT, JSON), chunking, embeddings, and retrieval
- Researcher, Data Analyst, and Webhook Inspector tools
- LangGraph orchestration: plan → investigate → aggregate → sufficiency → (retry or verify/write/critic)
- Verifier checks claims against evidence (unsupported, contradictory, missing, weak) and can request another investigation pass
- Critic reviews the draft report; the Writer cannot override verifier findings
- Deterministic merchant health score with factors, penalties, and recommendations — no ML model
- Production-style HTTP API with Pydantic schemas, request IDs, structured logs, and OpenAPI docs
- Investigation console (Next.js): trace pipeline, evidence, metrics, health, and report — no hidden chain-of-thought
- Safe execution traces (node, action, tool, query, evidence IDs, decision, verification) — no private chain-of-thought
- Docker Compose (Postgres + API + dashboard), container boot (wait / migrate / seed), CI lint-format-typecheck-test-compose smoke

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness (no database) |
| `GET` | `/health/ready` | Readiness (database ping) |
| `POST` | `/investigations` | Run an investigation |
| `GET` | `/investigations/{id}` | Fetch the report |
| `GET` | `/investigations/{id}/trace` | Fetch the execution trace |
| `GET` | `/merchants/{id}/health` | Explainable health score |
| `GET` | `/merchants/{id}/metrics` | Catalog payment metrics |
| `GET` | `/evidence/{id}` | Resolve a cited evidence item |
| `GET` | `/docs` | OpenAPI UI |

Every response includes `X-Request-ID`. Errors return `{error, detail, status_code, request_id}`. Local demo mode does not require API keys.

## Reproducible local setup

Python 3.11+ (3.12 in CI and Docker).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
ruff check packages apps tests
ruff format --check packages apps tests
mypy
pytest -q
./scripts/local-api.sh
```

`uvicorn` is installed in `.venv`. If the shell says `command not found: uvicorn`, the venv is not active — run `source .venv/bin/activate` first, or call `.venv/bin/uvicorn` directly.

Dashboard (separate terminal):

```bash
./scripts/local-web.sh
```

Open `http://localhost:3001`. The dashboard binds 3001 so it does not collide with other local apps on 3000. It proxies `/backend/*` to the API on port 8000. Sample questions use the synthetic Harbor Retail (`M102`) and Cedar Digital Goods (`M201`) incidents.

Or run the same checks as CI:

```bash
./scripts/check.sh
```

Apply migrations against Postgres, then persist chunks with pgvector:

```bash
alembic upgrade head
payops-seed
PAYOPS_VECTOR_BACKEND=pgvector payops-ingest
```

Synthetic ops docs live in `docs/corpus/`. Every chunk keeps `document_id`, source path, section, and original front matter.

## Docker

From a clean machine with Docker Compose v2:

```bash
docker compose -f docker/docker-compose.yml up --build
```

This starts Postgres, runs Alembic, seeds synthetic merchants if the database is empty, serves the API on `http://localhost:8000`, and the dashboard on `http://localhost:3001`. RAG uses the in-memory store inside the API container (no extra vector database). Postgres is not published to the host.

If those host ports are already in use:

```bash
PAYOPS_PUBLISH_API=18000 PAYOPS_PUBLISH_WEB=13001 docker compose -f docker/docker-compose.yml up --build
```

Docker Desktop needs several gigabytes of free disk. A full volume (`no space left on device`) will crash the Docker VM during image export. Free space, then **Quit** and reopen Docker — do not reset to factory defaults unless you intend to wipe local images and volumes.

Stop and remove volumes:

```bash
docker compose -f docker/docker-compose.yml down -v
```

## Validation commands

```bash
ruff check packages apps tests
ruff format --check packages apps tests
mypy
pytest -q
cd apps/web && npm ci && npm run typecheck
docker compose -f docker/docker-compose.yml up --build -d
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:3001/health
curl -fsS -X POST http://127.0.0.1:8000/investigations \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does GATEWAY_TIMEOUT mean?","max_iterations":2}'
docker compose -f docker/docker-compose.yml down -v
```
