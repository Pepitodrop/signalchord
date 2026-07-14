# Dependency outage runbook

Use this runbook when Kafka, PostgreSQL, Neo4j, Redis, object storage, OpenSearch, the OpenTelemetry collector or third-party notification delivery is degraded.

## First response

1. Assign incident commander and dependency owner.
2. Identify tenant, source, topic, consumer group and time-window scope.
3. Check the SignalChord overview dashboard for API errors, pipeline freshness, consumer lag and telemetry collector health.
4. Confirm whether telemetry is complete. If the collector is unavailable, preserve local application logs and provider metrics before restarting workloads.
5. Stop harmful side effects first: pause notification workers, feed collectors or replay jobs if duplication or data loss is possible.

## Diagnosis

- Kafka: broker health, controller health, topic availability, consumer lag, rebalance loops, producer error rate.
- PostgreSQL: connection saturation, lock waits, migration state, outbox age.
- Neo4j: connectivity, write latency, query latency, page-cache pressure, constraint failures.
- Object storage: bucket availability, request latency, permission errors, prefix listing/reads.
- OpenSearch: cluster health, rejected writes, index availability, query latency.
- OpenTelemetry: collector `up`, exporter send failures, dropped spans/metrics/logs.

## Recovery

Resume services in dependency order: telemetry, Kafka, authoritative stores, projectors, API/realtime, notification side effects. Run `scripts/smoke-test.sh` or the staging canary after recovery and attach dashboard evidence to the incident record.

## Abort conditions

Abort automated recovery when tenant isolation, data deletion guarantees, source rights, or notification suppression controls cannot be verified.
