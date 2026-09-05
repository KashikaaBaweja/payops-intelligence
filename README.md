# PayIntel AI

Agentic Payment Intelligence & Research Platform. Package names remain `payops_*` so existing imports and Docker images keep working.

This is **not a chatbot**. A user question runs a LangGraph investigation:

**query → plan → research → retrieve → evaluate evidence → more search if needed → data/ML if needed → transaction integrity if needed → critique → report**

The console shows sources, metrics, model quality, integrity checks, and a safe agent trace. It does not display private chain-of-thought.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) and [docs/adr/008-payintel-agents.md](docs/adr/008-payintel-agents.md).

## Current scope

- LangGraph orchestration with explicit state transitions; agents are typed Python classes, not one giant prompt
- Agentic RAG: query analysis → retrieve → relevance/rerank → rewrite if insufficient, capped by `PAYOPS_RAG_MAX_ITERATIONS`. Citations, latency, and search rounds are logged. No LLM answer step.
- Researcher formulates seed queries; Retrieval Agent executes `search_docs`; Hindi/English glossary expansion (not multilingual embeddings)
- Data Analyst catalog (allowlisted SQL) and Webhook Inspector
- ML Agent: selector routes classification (failure logistic) or capture-latency regression; holdout metrics are computed, never invented — not a fraud decision
- Transaction Integrity Agent: read-time consistency checks against schema invariants
- Live ledger transfer: debit/credit/journal in one SQL transaction with injectable rollback (`POST /transactions/transfers`)
- Verifier + Critic; Writer cannot override verifier findings
- Explainable merchant health scorecard
- Durable audit store (`investigation_runs`, `evidence_index`)
- Next.js console with pipeline, evidence, metrics, and report
- Docker Compose (Postgres + API + dashboard)

Default retrieval uses a hashing bag-of-words embedder. There is no LLM client and no LangChain runtime. Demo mode does not require API keys.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness (no database) |
| `GET` | `/health/ready` | Readiness (database ping) |
| `POST` | `/investigations` | Run an investigation |
| `GET` | `/investigations/{id}` | Fetch the report |
| `GET` | `/investigations/{id}/trace` | Fetch the execution trace |
| `GET` | `/merchants/{id}/health` | Explainable health score |
| `GET` | `/merchants/{id}/risk` | Failure-classifier score (alias of `/ml/classification`) |
| `GET` | `/merchants/{id}/ml/classification` | Failure-classifier score and holdout metrics |
| `GET` | `/merchants/{id}/ml/regression` | Capture-latency regressor score and holdout metrics |
| `POST` | `/merchants/{id}/risk/what-if` | Rescore a hypothetical payment (classifier only) |
| `GET` | `/merchants/{id}/metrics` | Catalog payment metrics |
| `GET` | `/evidence/{id}` | Resolve a cited evidence item |
| `GET` | `/transactions/accounts` | Ledger wallet balances |
| `POST` | `/transactions/transfers` | Debit/credit/ledger transfer (`fail_at` forces ROLLBACK) |
| `GET` | `/transactions/transfers/{id}` | Persisted transfer + audit events |
| `GET` | `/investigations` | List recent investigation runs |
| `GET` | `/documents` | Corpus files on disk |
| `GET` | `/health/services` | Live API, database, vector, LLM, agents, ML status |
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
