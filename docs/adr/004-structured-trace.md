# ADR-004: Structured traces, not raw chain-of-thought

Status: accepted

## Decision
Each node appends a `TraceEvent` with `node`, `action`, `tool`, `search_query`, `evidence_ids`, `decision`, and `verification_status`. Raw model scratchpads are not stored.

## Why
Ops and interviewers need an audit trail that is inspectable and safe to share. Private reasoning text is neither.
