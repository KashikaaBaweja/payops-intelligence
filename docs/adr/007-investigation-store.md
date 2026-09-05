# ADR-007: Durable investigation audit store

Status: accepted

## Decision
Investigation reports, traces, and cited evidence are written to `investigation_runs` and `evidence_index` in the same database as payments. The API store is a session-backed repository, not a process dict.

## Why
GET-after-restart and a second API worker must see the same run. That is the audit log. It is not a classroom ACID simulator.
