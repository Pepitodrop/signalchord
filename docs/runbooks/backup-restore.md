# Backup and Restore Runbook

Use this runbook for planned restore drills and emergency recovery. Do not run destructive restore commands without a maintenance window, written abort criteria, and a confirmed target namespace.

## Preconditions

- Confirm the incident or drill scope: tenant, source, topic, store, and time window.
- Preserve logs, DLQ records, offsets, object versions, database snapshots, and current image digests.
- Pause harmful side effects: notification workers, source adapters, affected consumers, replay jobs, or webhooks.
- Verify the restore target is isolated from customer traffic and external providers.
- Record operator, source environment, restore environment, Git SHA, image digests, start time, target RPO, and target RTO.

## Single-owner k3s profile

Create the supported checksummed backup with a MinIO client image pinned by digest:

```bash
python3 scripts/single-server/backup_restore.py backup \
  --namespace signalchord \
  --output /secure/backups/signalchord-$(date -u +%Y%m%dT%H%M%SZ) \
  --minio-client-image 'minio/mc@sha256:<verified-digest>'
```

The command captures:

- PostgreSQL in custom `pg_dump` format;
- an object-level mirror of the MinIO `raw-documents` bucket;
- application and community Helm values;
- non-secret Kubernetes workload, Service, storage, ingress, and NetworkPolicy inventory;
- Git SHA, timestamps, file sizes, and SHA-256 checksums.

It does not export the Kubernetes runtime Secret. Preserve the operator-created `runtime.env` separately in encrypted offline storage. The command suspends the feed collector and scales SignalChord application writers to zero, then restores their previous state even when collection fails.

Restore is destructive and requires an explicit target confirmation:

```bash
python3 scripts/single-server/backup_restore.py restore \
  --namespace signalchord \
  --backup /secure/backups/signalchord-20260716T120000Z \
  --minio-client-image 'minio/mc@sha256:<verified-digest>' \
  --confirm-namespace signalchord \
  --yes
```

The restore verifies every checksum before mutation, restores PostgreSQL, and replaces the MinIO bucket with the saved mirror. Kafka, Neo4j, OpenSearch, Valkey, Prometheus, and Grafana are explicitly not restored by this command. Run the relevant replay/rebuild procedures and Kubernetes acceptance afterward.

```bash
python3 scripts/single-server/acceptance.py \
  --namespace signalchord \
  --host signalchord.example.com \
  --canary \
  --fixture-image 'python@sha256:<verified-digest>'
```

Repository CI proves command structure, checksum behavior and Restricted Pod Security admission. It does not prove the target server's storage driver, available temporary space, backup duration, restore duration, or actual RPO/RTO. Record those through an isolated server drill.

## PostgreSQL

1. Restore the selected backup into an isolated database when possible.
2. Apply reviewed migrations forward only.
3. Run migration status, request specs, and the synthetic canary.
4. Reconcile tenant, source, watchlist, policy, alert, outbox, and delivery counts.
5. Record actual RPO/RTO and any missing outbox events.

## Kafka and derived stores

1. Record topic configs, partition counts, consumer offsets, DLQ counts, and schema versions.
2. Rebuild or replay with notification side effects disabled or ledgered.
3. Verify duplicate delivery does not create duplicate graph facts, alerts, or notifications.
4. Recreate Neo4j constraints and OpenSearch indexes before exposing query APIs.
5. Resume live consumers only after lag, DLQ rate, tenant isolation and reconciliation are acceptable.

For the personal single-server profile, Kafka, Neo4j and OpenSearch are treated as derived/rebuild stores unless separate tested offline backups are maintained.

## Abort conditions

Abort when checksums fail, tenant isolation fails, deletion tombstones are missing, source rights cannot be verified, restored data is older than the approved RPO, replay creates duplicate side effects, available maintenance storage is insufficient, or customer traffic could be affected.

## Evidence

Attach command logs, the backup manifest, restore report, timestamps, canary output, reconciliation tables, actual RPO/RTO and residual risks to issue #26 and the release checklist.
