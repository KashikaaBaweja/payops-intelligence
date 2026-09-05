# ADR-010: Live ledger transfer demonstrates ACID

Status: accepted

## Decision
PayIntel keeps two different integrity surfaces:

1. `validate_integrity` — read-time consistency checks on payments/orders (ADR-008).
2. `POST /transactions/transfers` — a real double-entry transfer on `ledger_*` tables.

The transfer is one database transaction:

`BEGIN → debit source → credit dest → write journal → COMMIT`

`fail_at` raises inside that transaction so the engine rolls back debit, credit, and journal together.

## Isolation
- SQLite: `IMMEDIATE` (`BEGIN IMMEDIATE`). Writers take a reserved lock before debit so a second transfer cannot interleave a lost update on the same wallet.
- PostgreSQL: `SERIALIZABLE`. Concurrent overdrafts cannot both commit.

## Why
A static ACID explainer does not prove rollback. The database must show unchanged balances after an injected credit failure, and a new connection must still see a committed transfer.
