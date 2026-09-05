# ADR-009: Bounded agentic RAG, not query → vector → LLM

Status: accepted

## Decision
Document questions run a retrieve → score → sufficiency → rewrite loop inside `run_agentic_rag`. The investigation writer still owns the report. The loop never calls an LLM and never emits private chain-of-thought.

## Loop
1. Analyze the query into error codes, topics, and tokens.
2. Retrieve top-k from the existing vector store.
3. Score relevance (vector floor + token overlap + facet match) and rerank.
4. If required facets are missing or nothing was kept, rewrite from unused seed queries or missing-facet templates.
5. Stop on sufficient evidence, rewrite exhaustion, or `PAYOPS_RAG_MAX_ITERATIONS`.

## Outputs
Safe metadata only: search index, query, rewrite reason, kept/rejected counts, latency, citations, grounded excerpt, conflict flag.

## Why not an LLM answer
A generated answer would skip citation enforcement and invent reasoning. The excerpt is assembled from ranked snippets plus evidence IDs.
