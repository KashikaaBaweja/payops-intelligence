# CI fix report — PayIntel AI / payops-intelligence

## ROOT CAUSE

GitHub Actions run `33986347848` on `aae7fc2` failed two jobs. Those failures were real. A third failure was waiting behind mypy.

1. **Python typecheck (first failing python step)**  
   `mypy` 2.3 rejected `packages/payops_core/query_language.py`. `normalize_language_choice` and `language_label` returned values from a `dict` / `str` path, so the return type was `str` instead of the declared `Literal` aliases.

2. **Docker smoke (first failing docker step)**  
   Compose came up, then the wait loop only polled `http://127.0.0.1:8000/health/ready`. Smoke immediately curled `http://127.0.0.1:3001/health` while the Next.js container was still binding. `curl` exited 56 (`Connection reset by peer`). The two JSON bodies in the log are API `/health` and `/health/ready` concatenated; the reset is the third curl to the web container.

3. **Pytest (would fail after mypy was fixed)**  
   The auth commit on `main` did not include the multilingual writer/state/glossary work already in the working tree. `WriterAgent.write()` rejected `query_language` / `response_language` / `retrieval_query`, so 16 graph tests failed until those files were restored.

4. **Eval DOC-03 (real retrieval bug, not a flaky assertion)**  
   The agentic RAG loop treated a topic as covered when the word appeared in any kept snippet. An unfiltered first search kept `refunds-faq` (and often stopped). The gold document is `refund-policy` (`docs/corpus/refunds.md`, frontmatter `doc_id: refund-policy`, `doc_type: refund_policy`). Topic-filtered seeds existed but never ran. The same early-stop also hid `payment-failures` / `incident-runbook` on ANOM-01 after error-code hits, because `"timeout"` is a substring of `GATEWAY_TIMEOUT`.

No secrets were required for these failures. Tests do not call Razorpay.

## FIX

- Return explicit `Literal` branches from `normalize_language_choice` and `language_label` (no `type: ignore`).
- Restore `WriterAgent.write()` language kwargs, investigation state fields, glossary expansions, and the multilingual / query-history tests that belong with them.
- Researcher: run error-code and topic-hint queries **before** the unfiltered planner/original question so the first retrieve uses the intended `doc_type` filter (`refund_policy`, `error_codes`, `runbook`, `webhook_docs`).
- Agentic loop: a topic with a `TOPIC_HINTS` `doc_type` is missing until a kept chunk actually has that `doc_type`. Token-in-blob is no longer enough.
- Docker CI: `docker compose up --build -d --wait`; wait until **both** API ready and web `/health` succeed; print a newline after each smoke curl; signup with a CI-only password that meets the strength rules (`Testuser1!x` is a test fixture, not a production secret); give the web healthcheck a longer start period.

Quality gates were not weakened. No step uses `|| true`. No tests were deleted.

## FILES CHANGED

- `.github/workflows/ci.yml`
- `docker/docker-compose.yml`
- `docker/Dockerfile.web`
- `packages/payops_core/query_language.py`
- `packages/payops_core/agents/writer.py`
- `packages/payops_core/agents/researcher.py`
- `packages/payops_core/graph/state.py`
- `packages/payops_core/rag/glossary.py`
- `packages/payops_core/rag/loop.py`
- `tests/unit/test_glossary.py`
- `tests/unit/test_query_language.py` (added; was missing from `main`)
- `tests/unit/test_query_input.py` (added; was missing from `main`)
- `tests/unit/test_researcher_agent.py`
- `tests/unit/test_agentic_rag.py`
- `tests/integration/test_multilingual_query.py` (added; was missing from `main`)
- `tests/integration/test_query_history.py` (added; was missing from `main`)
- `docs/CI_FIX_REPORT.md` (this file)

## TESTS RUN

```text
ruff check packages apps tests
ruff format --check packages apps tests
mypy
pytest -q
pytest -q
cd apps/web && npm run typecheck
cd apps/web && NEXT_TELEMETRY_DISABLED=1 npm run build
```

Targeted before the full suite:

```text
pytest -q tests/unit/test_researcher_agent.py tests/unit/test_agentic_rag.py tests/agent_eval/test_eval_suite.py
```

Docker compose was not re-run on this machine: the local Docker daemon did not respond. The docker workflow change matches the failing GitHub smoke log (curl 56 on `:3001/health` after API-only wait).

## RESULT

**PASS**

| Gate | Result |
| --- | --- |
| `ruff check` | pass |
| `ruff format --check` | pass (149 files) |
| `mypy` | pass (103 source files) |
| `pytest -q` run 1 | **200 passed** |
| `pytest -q` run 2 | **200 passed** |
| `npm run typecheck` | pass |
| `npm run build` | pass (Next.js 15.5.25, 32 pages) |

## CI STATUS

**READY**

The workflow still runs lint, format, mypy, the full pytest suite, web typecheck, compose build, and authenticated investigation smoke. Push these changes to `main` (or open a PR) to get a new GitHub Actions run. Desktop iCloud git mapping is unreliable; commit from a local working clone of `KashikaaBaweja/payops-intelligence` that contains these files.

## What to do after this fix

1. Confirm the files above are staged. Do not commit `.env` or real Razorpay / SMTP credentials.
2. Commit on a working git clone (not a timed-out iCloud `.git/index`).
3. `git push origin main` (or push a branch and open a PR).
4. Open [https://github.com/KashikaaBaweja/payops-intelligence/actions](https://github.com/KashikaaBaweja/payops-intelligence/actions).
5. Open the new `ci` run. All three jobs must be green:
   - **python** — Install → Lint → Format → Typecheck → Test
   - **web** — Install → Typecheck
   - **docker** — Compose up (with `--wait`) → Wait for API **and** web → Smoke (signup + investigation) → Compose down
6. If docker smoke fails again, the Compose up / wait step logs will show whether the web container is unhealthy. That is a remaining environment issue, not a hidden `|| true`.
