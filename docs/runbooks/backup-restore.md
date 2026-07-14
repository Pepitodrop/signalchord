# Backup and Restore Runbook

Use this runbook for planned restore drills and emergency recovery. Do not run production restore commands without an incident commander, dependency owner, and written rollback/abort criteria.

## Preconditions

- Confirm the incident or drill scope: tenant, source, topic, store, and time window.
- Preserve logs, DLQ records, offsets, object versions, database snapshots, and current image digests.
- Pause harmful side effects: notification workers, source adapters, affected consumers, replay jobs, or webhooks.
- Verify the restore target is isolated from production customers and providers.
- Record operator, approver, source environment, restore environment, git SHA, image digests, start time, target RPO, and target RTO.

## PostgreSQL

1. Restore the selected managed backup into an isolated database instance.
2. Apply reviewed migrations forward only.
3. Run `bin/rails db:migrate:status`, Rails request specs, and the synthetic canary against the restored control plane.
4. Reconcile tenant, source, watchlist, policy, alert, outbox, and notification-delivery counts against the incident window.
5. Record actual RPO/RTO and any missing outbox events.

## Kafka

1. Record topic configs, partition counts, consumer group offsets, DLQ counts, and schema registry versions.
2. Restore or mirror topics according to the provider procedure.
3. Replay through a dedicated replay group with notification side effects disabled or ledgered.
4. Verify duplicate delivery does not create duplicate graph facts, alerts, or notification deliveries.
5. Resume live consumers only after lag, DLQ rate, and reconciliation are within the approved threshold.

## Object Storage

1. Restore the tenant/source prefix into an isolated bucket or prefix.
2. Verify object hashes, metadata, retention labels, and deletion tombstones.
3. Confirm restored objects do not bypass current source-rights or deletion obligations.
4. Repoint staging workers only after legal/privacy constraints are confirmed.

## Neo4j

1. Restore the graph backup or rebuild from `graph.mutation-requested.v1` events in an isolated graph.
2. Apply graph constraints and indexes from `graph/migrations`.
3. Reconcile stable IDs, relationship counts, temporal validity, and tenant predicates.
4. Run graph-query tenant-isolation checks before exposing query APIs.

## OpenSearch

1. Drop and recreate the staging search indexes.
2. Rebuild from `document.normalized.v1`, `entity.resolved.v1`, `claim.clustered.v1`, and object storage.
3. Validate tenant-prefixed IDs, counts, freshness, query behavior, and p95 query latency.

## Abort Conditions

Abort when tenant isolation fails, deletion tombstones are missing, source rights cannot be verified, restored data is older than approved RPO, replay produces duplicate side effects, DLQ rate exceeds threshold, or production traffic could be affected.

## Evidence

Attach command logs, timestamps, dashboards, canary output, reconciliation tables, operator and approver names, actual RPO/RTO, and residual risks to issue #26 and the release checklist.
