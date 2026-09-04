# PayOps Intelligence — System Architecture

**Subtitle:** Autonomous AI Agent for Payment Operations, Merchant Research and Incident Investigation

> Disclaimer: This is an original system inspired by publicly known payment-platform concepts (payments, refunds, settlements, disputes, webhooks). It is not modeled on any company's internal architecture and uses 100% synthetic data.

---

## 1. Product Framing

The system answers operational investigation questions like:

> "Why did Merchant M102's payment success rate decrease between 10 AM and 12 PM, what caused the problem, what evidence supports the conclusion, and what should the operations team do?"

It behaves like a junior payments-ops analyst who can read docs, query metrics, inspect webhook logs, form a hypothesis, check their own work, and write a report — with every step auditable. The differentiator versus a "RAG chatbot" is: **multi-agent planning, tool-grounded evidence, self-critique, and a visible execution trace**, not just "search docs and answer."

---

## 2. High-Level Architecture

```
                              ┌─────────────────────────────┐
                              │        Frontend (Next.js)    │
                              │  Investigation UI + Timeline │
                              └──────────────┬───────────────┘
                                             │ REST/SSE
                              ┌──────────────▼───────────────┐
                              │        API Layer (FastAPI)    │
                              │  /investigations, /health,    │
                              │  /evidence, /reports          │
                              └──────────────┬───────────────┘
                                             │
                              ┌──────────────▼───────────────┐
                              │     LangGraph Orchestrator    │
                              │   (typed shared state graph)  │
                              └──────────────┬───────────────┘
              ┌───────────────┬──────────────┼──────────────┬────────────────┐
              ▼               ▼              ▼              ▼                ▼
        Planner Agent   Researcher Agent  Data Analyst   Incident/Risk   Evidence
                          (RAG)           Agent (SQL)     Agent          Sufficiency
                                                                          Agent
                                                                             │
                                                                    insufficient? loop
                                                                             │
                                                                             ▼
                                                                      Verifier Agent
                                                                             │
                                                                             ▼
                                                                       Critic Agent
                                                                             │
                                                                             ▼
                                                                       Writer Agent
                                                                             │
                                                                             ▼
                                                                     Final Report + Trace
              │
              ▼
  ┌───────────────────────┐   ┌────────────────────┐   ┌─────────────────────┐
  │ Vector Store (Chroma/  │   │ Postgres (synthetic│   │ Event Store          │
  │ pgvector) — docs        │   │ payments schema)    │   │ (webhook_events)     │
  └───────────────────────┘   └────────────────────┘   └─────────────────────┘
```

### Layering principles
- **API layer** invokes the orchestrator; it does not issue ad-hoc SQL or vector queries of its own.
- **Orchestrator (LangGraph)** owns control flow and shared state; it does not itself "reason" about payments — it delegates to agents.
- **Agents** are deterministic Python components with a narrow responsibility and a restricted toolset. Demo mode does not call an LLM for control flow.
- **Tools** are deterministic, typed, validated Python functions — the only path to data. Agents never get raw DB credentials or arbitrary SQL.

---

## 3. Component Responsibilities

### 3.1 Orchestrator Agent (LangGraph graph, not really an "agent" with its own LLM persona)
- Owns the `InvestigationState` typed object.
- Routes between nodes based on state (conditional edges).
- Enforces `max_iterations` to prevent infinite research loops.
- Emits trace events to the execution log at every node transition.

### 3.2 Planner Agent
- Input: raw user question.
- Output: structured `InvestigationPlan` — list of `Task` objects, each with `task_type` (`retrieve_docs`, `query_metrics`, `inspect_webhooks`, `compare_merchants`, …), rationale, and required evidence category.
- Uses a keyword planner with a strict Pydantic `InvestigationPlan` — no free text is allowed to leak into control flow.

### 3.3 Researcher Agent (Standard + Agentic RAG)
- Executes `retrieve_docs` tasks.
- Retrieval tool signature: `search_docs(query, filters: DocFilter, top_k)`.
- Metadata filters: `doc_type` (api_docs, runbook, refund_policy, error_codes, …), `product_area`, `recency`.
- Returns `EvidenceItem` objects: `{source, doc_id, section, chunk_id, score, text_snippet, metadata}`.
- Can be re-invoked by the Evidence Sufficiency Agent with a refined query (this is what makes it "agentic" rather than single-shot RAG).

### 3.4 Data Analyst Agent
- Executes `query_metrics` tasks via the **SQL Tool Gateway** (Section 5) — never raw SQL from the LLM.
- Available operations: success rate, failure rate, breakdown by method/error code, time-window comparison, merchant comparison, refund rate, dispute rate, webhook delivery failure rate.
- Returns typed `MetricResult` objects with numeric values, time windows, and the exact operation used (fully reproducible).

### 3.5 Incident/Risk Agent
- Consumes evidence + metrics gathered so far.
- Produces ranked `Hypothesis` objects: `{cause, supporting_evidence_ids[], confidence}`.
- Does not invent new evidence — it only correlates what Researcher/Data Analyst/webhook tool already returned.

### 3.6 Evidence Sufficiency Agent
- The core "agentic RAG" decision point.
- Input: current `EvidenceBundle` + original plan.
- Output: `SufficiencyVerdict { sufficient: bool, missing: List[EvidenceGap], next_action }`.
- If insufficient and `iterations < max_iterations` → route back to Researcher/Data Analyst with a refined sub-task.
- If insufficient and iterations exhausted → route to Writer with an explicit "evidence insufficient" flag (never silently guesses).

### 3.7 Verifier Agent
- Takes the Incident/Risk Agent's leading hypothesis and the draft claims.
- Checks each claim against `evidence_ids` — flags any claim without a supporting citation as `unsupported`.
- Can force one more Researcher/Data Analyst call if a specific claim needs backing.

### 3.8 Critic Agent
- Reviews the near-final report for completeness (does it answer the original question?), internal consistency, and unsupported conclusions.
- Can send the draft back to Writer once with specific revision instructions (bounded — max 1 revision loop to avoid oscillation).

### 3.9 Writer Agent
- Produces the final structured `IncidentReport` (schema in Section 8).
- Only allowed to reference evidence already present in `EvidenceBundle` — enforced by giving it a closed context, not open retrieval.

---

## 4. LangGraph State Machine

### 4.1 Shared State (conceptual)
```python
class InvestigationState(TypedDict):
    question: str
    merchant_id: str | None
    time_window: TimeWindow | None
    plan: InvestigationPlan | None
    evidence: EvidenceBundle          # docs + metrics + webhook findings, append-only
    hypotheses: list[Hypothesis]
    sufficiency: SufficiencyVerdict | None
    verified_claims: list[VerifiedClaim]
    critique: CritiqueResult | None
    report: IncidentReport | None
    trace: list[TraceEvent]           # observable reasoning trace
    iteration: int
    max_iterations: int
```

### 4.2 Graph edges
```
START → intake → planner → dispatch (parallel fan-out)
dispatch → researcher, data_analyst, webhook_inspector   (parallel, per plan tasks)
{researcher, data_analyst, webhook_inspector} → aggregate_evidence
aggregate_evidence → sufficiency_evaluator

sufficiency_evaluator --insufficient & iteration < max--> refine_tasks → dispatch
sufficiency_evaluator --insufficient & iteration >= max--> writer (flag: incomplete)
sufficiency_evaluator --sufficient--> incident_risk_agent

incident_risk_agent → verifier
verifier --unsupported claim, budget left--> refine_tasks → dispatch
verifier --ok / budget exhausted--> critic

critic --revise (max 1x)--> writer_revise → critic
critic --approved--> writer → END
```

- **Loop guard:** every loop-back increments `iteration`; a hard `max_iterations` (config, default 3) forces exit to Writer with an explicit "evidence insufficient" report rather than infinite looping.
- **Parallel fan-out** uses LangGraph's parallel branches with a join (`aggregate_evidence`) — this is where "multi-document retrieval + structured data analysis" run concurrently, demonstrating real orchestration rather than a linear chain.

---

## 5. Tooling Layer (deterministic, restricted)

### 5.1 SQL Tool Gateway
- Not a text-to-SQL system. A **fixed catalog of parameterized, pre-validated query templates** (e.g., `get_success_rate(merchant_id, window)`, `breakdown_by_error_code(merchant_id, window)`).
- Agent picks an operation name + typed parameters (validated via Pydantic) — never generates SQL strings itself.
- Enforces: allowed tables, row limits, timeout, read-only DB role.
- Rationale documented as an ADR (Section 12) — this is a deliberate security/production-quality decision reviewers will ask about.

### 5.2 RAG Retrieval Tool
- `search_docs(query, doc_type_filter?, top_k=5)` → vector search over chunked/embedded synthetic docs, with metadata carried through, optional cross-encoder rerank.

### 5.3 Webhook/Event Tool
- Query operations: `get_events_for_payment(payment_id)`, `get_delivery_failures(merchant_id, window)`, `find_duplicate_events(...)`, `find_delayed_events(threshold)`.
- Correlates `webhook_events` with `payments` on `payment_id`/`order_id`.

### 5.4 Merchant Health Tool
- Deterministic scoring function (not an LLM) combining: success rate, failure rate, refund rate, dispute rate, webhook reliability, recent anomaly severity — each weighted, each exposed individually in the output so the score is explainable, not a black box.

All tools return **typed Pydantic models**, are independently unit-testable, and are the only boundary through which agents touch data — this is the seam that makes the system safe to demo and safe to extend.

---

## 6. RAG Pipeline

```
raw docs (markdown/text)
  → parser (front-matter + section split)
  → cleaner (normalize whitespace, strip boilerplate)
  → chunker (section-aware, ~300–500 tokens, overlap)
  → metadata enrichment (doc_type, product_area, doc_id, section_title, version)
  → embedding (local sentence-transformers or OpenAI/Anthropic embeddings — pluggable)
  → vector store (Chroma for local dev; pgvector-compatible interface for prod parity)
  → retrieval (top_k + metadata filter)
  → optional rerank (cross-encoder, config-gated — demonstrates awareness without over-engineering MVP)
  → evidence formatter (attaches source/doc_id/section/chunk_id/score before it ever reaches an LLM prompt)
```

Evidence is **never** string-concatenated blindly into a prompt — it's passed as structured objects, and the Writer Agent is required (via prompt contract + a post-hoc citation checker) to reference `doc_id`/`chunk_id` for any factual claim.

---

## 7. Data Model (synthetic)

**Structured (Postgres):**
`merchants`, `payments`, `orders`, `refunds`, `settlements`, `disputes`, `webhook_events`, `payment_methods`, `error_codes`

Key relationships: `payments.order_id → orders`, `payments.merchant_id → merchants`, `refunds.payment_id → payments`, `webhook_events.payment_id → payments`, `disputes.payment_id → payments`. Timestamps designed so there are real, discoverable incidents (e.g., a synthetic gateway degrading a specific payment method for a specific merchant in a specific window, with matching webhook delivery delays).

**Unstructured (doc corpus):** API docs, failure-code reference, refund policy, settlement docs, webhook docs, error-code docs, merchant support articles, incident runbooks — all synthetic markdown, versioned, chunkable.

**Synthetic data generator:** a seedable script that plants 3–5 "known" incidents with ground-truth causes, used both for demo narratives and for the evaluation dataset (Section 10).

---

## 8. Final Report Schema

```python
class IncidentReport(BaseModel):
    executive_summary: str
    merchant_id: str
    incident_id: str
    time_window: TimeWindow
    severity: Literal["low", "medium", "high", "critical"]
    observed_metrics: list[MetricResult]
    findings: list[str]
    evidence: list[EvidenceRef]          # doc or metric refs, always resolvable
    likely_cause: Hypothesis
    alternative_hypotheses: list[Hypothesis]
    confidence: float                     # 0-1, derived from verifier/critic outcomes, not vibes
    recommended_actions: list[str]
    sources: list[EvidenceRef]
    agent_execution_summary: list[TraceEvent]
    evidence_sufficient: bool             # explicit — never silently overclaims
```

---

## 9. Observable Reasoning Trace (not chain-of-thought)

Every node appends a `TraceEvent` to `state.trace`:
```python
class TraceEvent(BaseModel):
    step: str                 # e.g. "researcher.search_docs"
    agent: str
    tool: str | None
    input_summary: str        # e.g. query text, params — not raw model reasoning
    output_summary: str       # e.g. "3 chunks retrieved, top score 0.81"
    timestamp: datetime
```
This satisfies the requirement for an audit trail (goal, plan, agents/tools invoked, queries, evidence IDs, verification status, retries, final confidence) **without** exposing private model reasoning — the trace is built from structured tool/agent I/O, not from raw LLM scratchpad text.

---

## 10. Evaluation Strategy

An eval dataset of investigation questions, each labeled with expected behavior:
1. Answer immediately (sufficient evidence in one pass)
2. Should trigger another retrieval
3. Should trigger a SQL query
4. Should trigger webhook inspection
5. Should end in "evidence insufficient" (deliberately unanswerable)

Metrics: retrieval relevance (precision@k against labeled relevant chunks), citation correctness (does cited doc_id actually support the claim), groundedness (% claims traceable to evidence), tool selection accuracy (did the planner pick the right task types), investigation completion rate, unsupported-claim rate (from Verifier), and agent loop efficiency (iterations used vs. minimum required). Implemented as a pytest-based harness that runs the graph in a "replay/record" mode against the seeded synthetic incidents, so it's deterministic and CI-runnable.

---

## 11. Risks & Tradeoffs

| Risk | Mitigation |
|---|---|
| LLM cost/latency from many agent hops | Cap `max_iterations`; use small/cheap model for routing-style agents (Planner, Sufficiency), reserve stronger model for Writer/Critic |
| Over-engineering for a portfolio project | Explicit MVP scope (Section 13); advanced features clearly deferred |
| Text-to-SQL hallucination/injection risk | Rejected outright — fixed parameterized query catalog instead |
| Non-determinism making tests flaky | Deterministic tools + fixture-seeded DB + evaluation harness runs against known synthetic incidents, not live LLM randomness for tool logic |
| Infinite agent loops | Hard iteration cap enforced at graph level, not agent-level (can't be prompted around) |
| Vector store complexity for a demo | Chroma embedded mode for local/dev; interface abstracted so pgvector swap is a config change, not a rewrite |
| Scope creep across 9 agents | Each agent is a thin LLM-call wrapper + schema; shared infra (LLM client, tracing, retry) is common code, not duplicated per agent |

---

## 12. Architecture Decision Records (planned)
- ADR-001: Why LangGraph over a hand-rolled state machine or a single ReAct agent.
- ADR-002: Why a fixed SQL template catalog instead of text-to-SQL.
- ADR-003: Why Chroma for MVP with an abstracted vector-store interface.
- ADR-004: Why the reasoning trace is built from structured events, not raw model transcripts.
- ADR-005: Iteration cap strategy and where it's enforced.

---

## 13. Minimum Viable Version (Phase target)

- Postgres schema + synthetic data generator (small but realistic: ~5 merchants, ~2–3k payments, a few planted incidents).
- Doc corpus (6–8 synthetic docs) + chunking/embedding/retrieval pipeline (no rerank yet).
- SQL Tool Gateway with 4–5 core operations (success rate, failure breakdown, error-code breakdown, time-window comparison).
- LangGraph graph with: Planner → Researcher + Data Analyst (parallel) → Sufficiency (single loop, max_iterations=1) → Writer. Verifier/Critic can be stubbed initially and filled in Phase-by-phase.
- FastAPI endpoint `POST /investigations` returning the report + trace synchronously.
- Minimal frontend: input box, trace timeline, report view (can be a simple React page before the "professional dashboard" polish).

## 14. Advanced Features (post-MVP)
- Full Verifier + Critic loop with bounded revision.
- Reranking stage in RAG.
- Webhook correlation tool + Incident/Risk Agent hypothesis ranking.
- Explainable merchant health score endpoint + dashboard widget.
- SSE streaming of trace events to the frontend (live investigation feed).
- Full evaluation harness + CI gate on groundedness/unsupported-claim thresholds.
- Docker Compose (API + Postgres + vector store) + CI pipeline.

---

## 15. Repository Structure (proposed)

```
payops-intelligence/
├── apps/
│   ├── api/                       # FastAPI service
│   │   ├── main.py
│   │   ├── routers/
│   │   └── deps.py
│   └── web/                       # Next.js dashboard
├── packages/
│   └── payops_core/                # installable Python package
│       ├── agents/
│       │   ├── planner.py
│       │   ├── researcher.py
│       │   ├── data_analyst.py
│       │   ├── incident_risk.py
│       │   ├── sufficiency.py
│       │   ├── verifier.py
│       │   ├── critic.py
│       │   └── writer.py
│       ├── graph/
│       │   ├── state.py            # InvestigationState + typed models
│       │   ├── nodes.py
│       │   └── build_graph.py
│       ├── tools/
│       │   ├── sql_gateway.py
│       │   ├── rag_retrieval.py
│       │   ├── webhook_tool.py
│       │   └── merchant_health.py
│       ├── rag/
│       │   ├── parsing.py
│       │   ├── chunking.py
│       │   ├── embeddings.py
│       │   └── vector_store.py
│       ├── data/
│       │   ├── schema.sql
│       │   ├── synthetic_generator.py
│       │   └── seed.py
│       ├── models/                 # Pydantic schemas shared across layers
│       └── config.py
├── docs/
│   ├── architecture/ARCHITECTURE.md
│   ├── adr/
│   └── corpus/                     # synthetic markdown documentation set
├── eval/
│   ├── dataset.jsonl
│   └── run_eval.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── agent_eval/
├── docker/
│   ├── Dockerfile.api
│   └── docker-compose.yml
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

---

## 16. Implementation Phases

Delivered as Git history on `main`:

| Phase | Deliverable |
|---|---|
| 1 | Repo scaffold, config, `.env.example`, CI skeleton |
| 2 | PostgreSQL-compatible payment operations data model + Alembic |
| 3 | Seedable synthetic dataset and planted incidents |
| 4 | Document ingestion (parse → clean → chunk) |
| 5 | Vector retrieval with source metadata |
| 6 | Research agent |
| 7 | Payment analytics SQL catalog |
| 8 | Webhook investigation tools |
| 9 | LangGraph investigation orchestrator |
| 10 | Evidence verification and critic loop |
| 11 | Explainable merchant health scoring |
| 12 | Investigation HTTP APIs |
| 13 | Investigation dashboard |
| 14 | Agent evaluation benchmark |
| 15 | Docker Compose, health checks, CI lint/type/test |
| 16 | Architecture and agent-design documentation |

## 17. Testing Strategy
- **Unit tests**: every tool (SQL gateway ops, webhook queries, chunker, embedder interface, merchant health scoring) tested in isolation with fixture data — no LLM calls.
- **Integration tests**: graph run end-to-end against a seeded test DB + test vector store, asserting on state shape (not LLM wording).
- **Agent evaluation tests**: the eval harness run against labeled synthetic incidents, asserting tool selection, grounding, citations, completion, and loop termination. No paid model is required.
- **Contract tests** on Pydantic schemas at every agent boundary (planner output, evidence bundle, report) to catch schema drift early.

## 18. Demo Strategy
- Seed 3 "headline" incidents (UPI `GATEWAY_TIMEOUT` on Harbor Retail M102, webhook delays on Cedar Digital Goods M201, sparse volume on Low-volume Labs M305) so the demo can show: (1) a clean successful investigation, (2) a loop-back-and-recover case, (3) an honest "I don't have enough evidence" case.
- Dashboard walkthrough: submit question → inspect the trace pipeline → read evidence, metrics, health, and the final report.

Local demo does not require LLM API keys.
