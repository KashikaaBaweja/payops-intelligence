# ADR-001: LangGraph for orchestration

Status: accepted

## Decision
The investigation is a typed state machine with parallel retrieval/analysis and bounded loops. LangGraph owns control flow; agents do not call each other.

## Why not a single ReAct agent
A free-form ReAct loop can skip verification, invent SQL, or loop forever. Reviewers need an explicit graph: plan → retrieve/query → sufficiency → (optional loop) → verify → write.

## Why not a hand-rolled FSM
The graph is small enough to write by hand, but LangGraph gives conditional edges, compiled execution, and a state object that matches the architecture doc without extra plumbing.
