# PayOps Intelligence

Autonomous investigation agent for payment operations. It answers questions like:

> Why did merchant M102's payment success rate drop between 10:00 and 12:00, what evidence supports that, and what should ops do?

The system is a typed LangGraph of specialist agents. Agents can only touch data through a fixed SQL catalog, document retrieval, and webhook queries. They never generate raw SQL. Every report includes a structured execution trace and an explicit `evidence_sufficient` flag.

All merchant, payment, and document data is synthetic.

## What it demonstrates

- Multi-agent planning with a bounded research loop
- Tool-grounded evidence (docs + metrics + webhooks)
- Self-critique and claim verification
- Honest "insufficient evidence" instead of a hallucinated root cause
- Explainable merchant health scoring

## Architecture

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) and [docs/adr](docs/adr).

Headline demo incidents (seeded, deterministic):

| Merchant | Window | What you should see |
|---|---|---|
| M102 Harbor Retail | 15 Jun 2024 10:00–12:00 | UPI `GATEWAY_TIMEOUT` spike |
| M201 Cedar Digital Goods | 18 Jun 2024 14:00–16:00 | Payments succeeded; webhooks were delayed |
| M305 Low-volume Labs | 1 May 2024 | Evidence insufficient |

## Quick start

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m payops_core.data.seed
pytest -q
```

Run the API:

```bash
uvicorn apps.api.main:app --reload --port 8000
```

Run the dashboard:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The UI proxies `/backend/*` to the API.

Default LLM mode is `demo`: the full graph runs without an API key, still calling real tools against the seeded database. Set `PAYOPS_LLM_PROVIDER=openai` and `OPENAI_API_KEY` to use a live model.

## HTTP API

- `GET /health`
- `POST /investigations` body: `{ "question", "merchant_id", "start", "end" }`
- `GET /merchants/{merchant_id}/health`

## Tests and eval

```bash
pytest -q
python eval/run_eval.py
```

## Docker

```bash
cd docker
docker compose up --build
```

Postgres is optional. SQLite is the default local store.
