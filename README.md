# PayOps Intelligence

Autonomous investigation agent for payment operations. This repository is at **Phase 1**: project foundation only.

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Current scope

- Python package layout
- FastAPI process with `/health`
- Shared Pydantic models
- Environment-based configuration and logging
- Docker / Compose skeletons
- Frontend placeholder

Agents, RAG, SQL tools, and synthetic data are intentionally not implemented yet.

## Quick start

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
PYTHONPATH=packages:. uvicorn apps.api.main:app --reload --port 8000
```

`GET http://localhost:8000/health` should return `{"status":"ok",...}`.

Frontend placeholder:

```bash
cd apps/web
npm install
npm run dev
```

## Docker

```bash
cd docker
docker compose up --build
```

## Next

Phase 2 will add the data model, synthetic generator, and seed script. Do not add agents until that layer exists.
