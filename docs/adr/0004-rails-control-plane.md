# ADR 0004 — Rails owns the transactional control plane

**Status:** Accepted

## Decision
Rails/PostgreSQL owns users, tenancy, RBAC, source policies, watchlists, investigations, policies, billing, notifications and audit metadata. Domain events are written through a transactional outbox.

## Consequences
Streaming work remains in Kafka services; Sidekiq is limited to control-plane jobs. Rails stores graph stable IDs but never duplicates graph facts.
