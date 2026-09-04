# ADR-005: Iteration cap at the graph

Status: accepted

## Decision
`max_iterations` is enforced in graph routing, not in agent prompts. Exhaustion routes to Writer with `evidence_sufficient=false`.

## Why
Prompt-level "please stop" can be ignored. A graph edge cannot.
