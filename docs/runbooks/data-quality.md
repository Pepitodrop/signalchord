# Data-quality incident runbook

Use this runbook for stale data, projection drift, duplicate alerts, missing provenance, model-quality regressions, or source content that appears corrupted or unlicensed.

## Triage

1. Record correlation IDs, event IDs, tenant IDs, source IDs and affected time windows.
2. Check pipeline freshness, event processing errors, graph mutation counts, OpenSearch projection counts and alert projection counts.
3. Compare authoritative Kafka/object-storage records with PostgreSQL alerts, Neo4j graph facts and OpenSearch documents.
4. Pause affected source adapters, projectors or notifications if bad data could reach users.

## Repair

- Prefer append-only correction events and replay-safe projectors.
- Use `docs/runbooks/replay.md` for controlled reprocessing.
- Preserve original source documents where rights permit and attach provenance to repairs.
- Do not erase history to hide a bad extraction, relationship or alert.

## Exit criteria

The incident commander confirms source counts, graph/search projections, alert state and customer-visible summaries are reconciled. A follow-up issue records the detection gap, metric or dashboard panel that should catch the class of failure earlier.
