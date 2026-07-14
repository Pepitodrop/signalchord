# Rollback and Forward-Repair Runbook

Use this runbook when a deployment, migration, graph change, or event-contract change must be rolled back or repaired.

## Stateless Rollback

1. Identify the exact failed image digest, previous known-good digest, Helm release revision, git SHA, and release manifest.
2. Pause source collection, replay jobs, and notification side effects when duplicate or harmful outputs are possible.
3. Run the pre-rollback canary and record current failures.
4. Roll back Helm to the previous immutable digest or release revision. Do not rebuild or retag images.
5. Run the post-rollback canary, tenant-isolation checks, and dependency health checks.
6. Record rollout history, image digests, canary output, and operator approval.

## Database Changes

Prefer forward-compatible migrations. Do not drop columns, rewrite primary identifiers, or delete business data in the same release that introduces readers or writers.

If an irreversible migration fails:

1. Stop affected writers.
2. Restore only when a tested backup and incident commander approval exist.
3. Otherwise ship a forward-repair migration that preserves existing data, marks corrupted rows, and appends audit evidence.
4. Re-run Rails specs, migration status, synthetic canary, and affected API checks.

## Event Contracts

Protobuf changes must remain backward-compatible. If a producer emits incompatible events:

1. Stop the producer and affected consumers.
2. Preserve invalid events in the DLQ or quarantine topic.
3. Deploy a compatible producer or translation consumer.
4. Replay quarantined events with original IDs, correlation IDs, idempotency keys, and operator metadata.
5. Run schema compatibility checks before resuming live flow.

## Graph and Search

Graph mutations are repaired with additive or temporal correction events. Avoid deleting graph history unless legal/privacy deletion requires it and the deletion workflow has approval.

OpenSearch is rebuildable. Prefer dropping and rebuilding search indexes from authoritative records over attempting partial manual repair.

## Required Evidence

Record failed revision, rollback target digest, commands, timestamps, canary output, tenant-isolation result, affected tenants/sources, replay ranges, forward-repair migrations or translation consumers, and residual-risk owner.
