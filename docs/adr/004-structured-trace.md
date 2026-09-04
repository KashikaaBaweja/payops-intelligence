# ADR-004: Structured traces, not raw chain-of-thought

Status: accepted

## Decision
Each node appends a `TraceEvent` with step, agent, tool, and input/output summaries. The UI shows this log. Raw model scratchpads are not stored.

## Why
Ops and interviewers need an audit trail that is inspectable and safe to share. Private reasoning text is neither.
