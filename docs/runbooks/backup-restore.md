# Backup and Restore Runbook

Use this runbook for planned restore drills and emergency recovery. Do not run production restore commands without an incident commander, dependency owner, and written rollback/abort criteria.

## Preconditions

- Confirm the incident or drill scope: tenant, source, topic, store, and time window.
- Preserve logs, DLQ records, offsets, object versions, database snapshots, and current image digests.
- Pause harmful side effects: notification workers, source adapters, affected consumers, replay jobs, or webhooks.
- Verify the restore target is isolated from production customers and providers.
- Record operator, approver, source environment, restore environment, git SHA, image digests, start time, target RPO, and target RTO.

## Single-owner k3s profile

The repository-supported single-server command is:

```bash
python3 scripts/single-server/backup_restore.py backup \
  --namespace signalchord \
  --output /secure/backups/signalchord-$(date -u +%Y%m%dT%H%M%SZ) \
  --minio-client-image 'minio/mc@sha256:<verified-digest>'
```

This command creates a checksummed maintenance backup of:

- PostgreSQL in custom `pg_dump` format;
- the MinIO `raw-documents` bucket through an object-level mirror;
- application and community Helm values;
- non-secret Kubernetes workload, Service, storage, ingress, and NetworkPolicy inventory;
- backup format, timestamp, Git SHA, file sizes, and SHA-256 checksums.

It does not export the Kubernetes runtime Secret. Preserve the operator-created `runtime.env` separately using encrypted offline storage. The command suspends the feed collector and scales SignalChord application Deployments to zero while collecting authoritative data, then restores the previous replica and schedule state.

Verify the backup directory is stored outside the single server and test its checksums before relying on it.

Restore requires a maintenance window and explicit target confirmation:

```bash
python3 scripts/single-server/backup_restore.py restore \
  --namespace signalchord \
  --backup /secure/backups/signalchord-20260716T120000Z \
  --minio-client-image 'minio/mc@sha256:<verified-digest>' \
  --confirm-namespace signalchord \
  --yes
```

The restore fails before mutation when a file is missing or a checksum differs. It restores PostgreSQL and replaces the target MinIO bucket with the saved object mirror. It intentionally does not restore Kafka, Neo4j, OpenSearch, Valkey, Prometheus, or Grafana. Run replay/rebuild procedures and the Kubernetes acceptance command after restore:

```bash
python3 scripts/single-server/acceptance.py \
  --namespace signalchord \
  --host signalchord.example.com \
  --canary \
  --fixture-image 'python@sha256:<verified-digest>'
```

A repository CI pass proves command structure, checksum handling, Restricted Pod Security admission, and fixture cleanup behavior. It does not prove the server's storage driver, available ephemeral space, backup duration, restore duration, or real RPO/RTO. Record those from an actual isolated drill.

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

For the single-server community profile, Kafka is not included in the authoritative backup. Treat Kafka loss as a rebuild/replay event and do not resume notifications until idempotency and reconciliation checks pass.

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

Neo4j Community in the personal single-server profile is treated as derived state unless a separate tested offline volume backup is maintained.

## OpenSearch

1. Drop and recreate the staging search indexes.
2. Rebuild from `document.normalized.v1`, `entity.resolved.v1`, `claim.clustered.v1`, and object storage.
3. Validate tenant-prefixed IDs, counts, freshness, query behavior, and p95 query latency.

## Abort Conditions

Abort when tenant isolation fails, deletion tombstones are missing, source rights cannot be verified, restored data is older than approved RPO, replay produces duplicate side effects, DLQ rate exceeds threshold, checksums fail, available maintenance storage is insufficient, or production traffic could be affected.

## Evidence

Attach command logs, the generated backup manifest and restore report, timestamps, dashboards, canary output, reconciliation tables, operator and approver names, actual RPO/RTO, and residual risks to issue #26 and the release checklist.
