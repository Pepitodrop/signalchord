# ADR 0002 — Neo4j owns relationship truth

**Status:** Accepted

## Decision
Neo4j is authoritative for graph relationships, temporal validity, evidence links and graph-derived topology. PostgreSQL stores only product/control-plane records and stable graph identifiers.

## Consequences
No relational graph mirror is permitted. Mutations use parameterized, idempotent `MERGE`; clients use approved bounded query templates. Search indexes are disposable projections.
