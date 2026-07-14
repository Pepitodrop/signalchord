# Recovery Architecture

SignalChord recovery treats data stores differently depending on whether they are authoritative or rebuildable. A green repository check does not prove disaster recovery. Issue #26 remains open until restore, replay, rebuild, and rollback drills have been run in an isolated staging environment with managed dependencies.

## Source of Truth

The repository-owned recovery matrix lives in `recovery/recovery-matrix.json` and is validated by `scripts/validate_recovery.py`.

Authoritative stores:

- PostgreSQL: tenants, users, RBAC, sources, watchlists, policies, alerts, notification delivery ledger, and transactional outbox.
- Kafka: retained processing history and replay checkpoints inside configured retention windows.
- Object storage: permitted raw document bytes, fetch metadata, and deletion tombstones.
- Neo4j: graph nodes, relationships, temporal validity, evidence links, and graph-derived signals.
- Secrets and configuration: runtime secret references, workload identity bindings, environment configuration, and provider IAM state.

Rebuildable stores:

- OpenSearch: disposable search projection rebuilt from normalized documents, entity/claim events, and object storage.
- Redis: disposable cache, rate-limit, and subscription state with no durable business records.

## RPO and RTO

The matrix records target RPO/RTO values and owners for each dependency. These are repository targets, not achieved production guarantees. The release gate requires drill evidence with actual recovery timestamps, source environment, restored environment, git SHA, image digests, operator, approver, and residual-risk acceptance.

## Recovery Validation

Every recovery drill must finish with:

- `scripts/smoke-test.sh` or the staging article-to-alert canary;
- tenant-isolation request checks;
- Kafka lag and DLQ review;
- stable-ID reconciliation across PostgreSQL, Kafka, object storage, Neo4j, and OpenSearch;
- proof that notification side effects were disabled or routed to a replay-safe ledger during replay;
- evidence retained in the release checklist.

## Derived Rebuilds

OpenSearch must be rebuilt from authoritative events and object storage rather than restored as a source of truth. A rebuild is not complete until tenant-prefixed document/entity/claim IDs reconcile, query results pass tenant filters, and freshness/latency dashboards recover.

Redis recovery is service restart plus reconnect verification. Any workflow that depends on Redis for durable business state is a release blocker.

## Rollback and Forward Repair

Stateless services roll back only to previously built immutable image digests. Do not rebuild from source during production rollback. Database migrations and event contracts are forward-compatible by default; irreversible changes require a forward-repair procedure, affected consumer pause plan, replay notes, and explicit release approval before deployment.

## External Evidence Still Required

Issue #26 cannot close until staging provides:

- PostgreSQL restore drill from a fresh environment;
- Kafka replay and duplicate-delivery drill;
- object-storage tenant-prefix restore drill with deletion tombstones intact;
- Neo4j restore or graph rebuild drill;
- OpenSearch rebuild validation against authoritative records;
- rollback by immutable digest with pre/post canaries;
- business/security approval of any RPO/RTO residual risk.
