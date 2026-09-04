# ADR-002: Fixed SQL catalog, not text-to-SQL

Status: accepted

## Decision
The Data Analyst picks an operation name and typed parameters. The SQL Tool Gateway runs a pre-validated template. LLMs never generate SQL strings.

## Consequences
- No injection via generated SQL
- Operations are unit-testable without an LLM
- New questions require a new catalog entry rather than hoping the model writes a correct join
