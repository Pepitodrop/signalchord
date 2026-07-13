# ADR 0006 — Clients use approved graph-query templates

**Status:** Accepted

## Decision
Clients never send arbitrary Cypher. An internal query boundary selects versioned templates, injects tenant predicates, validates parameter types and enforces depth, result, memory and time budgets.

## Consequences
New graph capabilities require reviewed templates. This reduces flexibility but materially improves tenant isolation, predictability and auditability.
