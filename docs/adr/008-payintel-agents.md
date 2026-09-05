# ADR-008: PayIntel agents on the existing investigation graph

Status: accepted

## Decision
The product name is PayIntel AI. The eight advertised agents map onto the shipped LangGraph FSM and catalog tools. New work is incremental wrappers and one integrity catalog. Existing planner, writer, verifier, SQL gateway, and hashing retriever stay.

| Product agent | Implementation |
|---|---|
| Orchestrator | `packages/payops_core/graph/build.py` |
| Research | `ResearcherAgent` (query formulation + relevance) |
| Retrieval | `RetrievalAgent` → `search_docs` |
| Data Analyst | `DataAnalystAgent` / `SqlToolGateway` |
| ML | `MLAgent` → `score_risk` or `score_regression` |
| Transaction Integrity | `TransactionIntegrityAgent` → `validate_integrity` |
| Critic/Verifier | `VerifierAgent` then `CriticAgent` |
| Report Writer | `WriterAgent` |

## What this is not
- Not a LangChain ReAct loop. There is no LLM in demo mode, so LangChain is not appropriate.
- Not multilingual *semantic* retrieval. Hindi questions get glossary term expansion onto the English corpus.
- The investigation integrity agent is still read-time consistency against CHECK/FK invariants. Live commit/rollback is `POST /transactions/transfers` (ADR-010), not `validate_integrity`.
- Not private chain-of-thought. Traces stay `{node, action, tool, query, evidence_ids, decision, verification}`.
