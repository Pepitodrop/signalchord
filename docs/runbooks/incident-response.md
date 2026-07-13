# Incident response

## Severity

- SEV-1: cross-tenant exposure, credential compromise, destructive data loss, uncontrolled sensitive notification or widespread unavailability.
- SEV-2: major ingestion/graph/alert outage, sustained data corruption risk or large replay backlog.
- SEV-3: partial degradation, isolated source failure, elevated latency or bounded DLQ increase.

## First 15 minutes

1. Assign incident commander, operations lead and communications owner.
2. Preserve evidence and correlation IDs; do not delete logs or DLQ records.
3. Stop harmful side effects first: pause notifications, source adapters, affected consumers or connectors.
4. Establish tenant/source/topic/time scope.
5. Rotate/revoke credentials if compromise is possible.
6. Record every command and decision in the incident timeline.

## Diagnostic order

Kafka broker/controller health, producer errors, consumer lag, Schema Registry compatibility, connector state, DLQ rate, object-store availability, NLP latency/errors, Neo4j write/query latency, Rails API authorization/audit, realtime connections and notification delivery ledger.

## Data integrity

Compare stable IDs and event counts across Kafka, object storage, Neo4j, PostgreSQL and OpenSearch. Source documents remain immutable where rights permit. Retractions and repair mutations append provenance; do not erase history to hide an incident.

## Recovery

Use the replay runbook, restore from tested backups where necessary, run the synthetic vertical-slice canary, validate tenant isolation and obtain incident-commander approval before resuming notifications.

## Post-incident

Within five business days, publish a blameless review covering timeline, customer/source impact, root cause, contributing controls, detection gap, recovery metrics, follow-up owners and dates. Security/privacy incidents follow applicable legal-notification procedures.
