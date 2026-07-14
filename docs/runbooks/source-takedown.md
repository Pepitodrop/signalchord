# Source takedown runbook

Use this runbook when a source owner, legal reviewer, privacy reviewer or customer requests source removal, deletion, retention change or collection suspension.

## Intake

1. Record requester, authority, source ID, tenant scope, requested action and deadline.
2. Preserve the request in the governance evidence store; do not paste private legal correspondence into public issues.
3. Disable affected source collection before deletion work if continued collection may violate rights.

## Execution

1. Identify raw object keys, normalized text objects, Kafka event windows, graph facts, search documents, alerts and notification records derived from the source.
2. Apply retention/deletion workflows from `docs/data-governance.md`.
3. Rebuild derived projections when deletion tombstones or source-rights changes require it.
4. Verify no enabled source still points to the prohibited endpoint or adapter.

## Verification

Attach evidence for source disablement, raw/derived deletion or retention exception, projection rebuild status, customer notification decision and privacy/legal approval. Keep issue #30 open until real legal/privacy approval and deletion-drill evidence exist.
