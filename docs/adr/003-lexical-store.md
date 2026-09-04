# ADR-003: Lexical vector interface for MVP

Status: accepted

## Decision
MVP retrieval is a TF-IDF/lexical store behind `search_docs`. The interface is store-agnostic so Chroma or pgvector can replace the backend without changing agents.

## Why
A local demo must run without embedding API keys. Lexical search is enough for a small synthetic corpus and keeps tests deterministic.
