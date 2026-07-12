# Kafka replay runbook

## Preconditions

- Approved change ticket and owner.
- Exact topic, partitions, event-time window and tenant scope.
- Verified idempotency behavior and destination capacity.
- Current consumer offsets, connector status, DLQ counts and graph/database backups.
- Notification side effects disabled or routed to a replay-safe ledger.

## Procedure

1. Pause the target consumer group or connector and record offsets/checkpoints.
2. Create a dedicated replay group ID; never reuse the live group while diagnosing.
3. Start from explicit offsets or timestamps and rate-limit consumption.
4. Preserve original event IDs, correlation IDs and source event time; add replay ID and operator metadata.
5. Observe lag, error rate, destination write latency, duplicate count and DLQ output.
6. Reconcile source records against object, search, PostgreSQL and graph projections.
7. Resume live consumers from the agreed checkpoint.
8. Record final offsets, counts, exceptions and evidence in the audit log.

## Neo4j connector replay

Pause CDC source before replaying graph mutations. Replay `graph.mutation-requested.v1` through a dedicated sink connector/group using idempotent `MERGE`. Verify stable-ID counts and relationship versions, then resume CDC from the recorded selector/checkpoint. Origin and processing-stage metadata must prevent source/sink loops.

## Abort conditions

Abort when tenant isolation fails, DLQ rate exceeds the approved threshold, destination latency threatens live traffic, external notifications escape the replay ledger, or reconciliation diverges beyond the pre-agreed tolerance.
