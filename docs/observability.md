# Observability specification

All services must emit OpenTelemetry traces, metrics and structured logs with `event_id`, `event_type`, `correlation_id`, `causation_id`, `processing_stage`, service/version and replay ID. `tenant_id` is allowed only where telemetry storage and dashboards are access-controlled. Logs must not include bearer tokens, source document bodies, notification device tokens, raw secrets, private keys or customer exports.

## Critical journeys and SLOs

These are internal starting targets, not customer commitments. They become production SLOs only after staging evidence and owner approval.

| Journey | SLI | Initial objective | Primary alert |
|---|---|---|---|
| Control-plane API availability | Non-5xx API responses / all API responses | 99.9% monthly | `SignalChordApiAvailabilityBurn` |
| Article-to-alert freshness | Age of newest event at each pipeline stage from source discovery through alert projection | 95% of permitted feed articles graph-visible within 5 minutes | `SignalChordPipelineFreshnessLag` |
| Durable alert delivery | High-severity alerts written to the durable inbox after policy request | 99% within 1 minute | `SignalChordNotificationDeliveryFailures` |
| Realtime delivery | Authenticated SSE sessions receive tenant-authorized events without slow-consumer drops | 99% of active sessions without dropped messages over 5 minutes | dashboard and realtime drop counters |
| Tenant isolation | Cross-tenant read/write/subscribe/infer/trigger violations | zero tolerated events | `SignalChordCrossTenantViolation` |
| Telemetry availability | OTEL collector up and Prometheus scraping collector metrics | 99.9% while application is available | `SignalChordTelemetryCollectorDown` |

## Correlation and traces

Every request/document/event should be traceable by `correlation_id` across source discovery, fetch, normalization, NLP, entity resolution, claim intelligence, graph mutation, policy evaluation, alert projection, notification delivery and realtime fanout. Kafka events already carry `correlation_id`, `causation_id` and `traceparent`; HTTP APIs must preserve request IDs in logs and responses. Replay operations add replay ID/operator metadata without replacing original event IDs.

Trace sampling starts at 10% for routine traffic and 100% for errors, replays, policy uploads, tenant-isolation counters, notification delivery failures and source deletion workflows. Production sampling changes require an issue comment with before/after storage estimates.

## Dashboards and alerts

Versioned repository assets:

- Prometheus scrape/rule config: `infrastructure/monitoring/prometheus.yml`, `infrastructure/monitoring/prometheus-rules/signalchord-alerts.yml`.
- Grafana provisioning and dashboard: `infrastructure/monitoring/grafana/provisioning/datasources/prometheus.yml`, `infrastructure/monitoring/grafana/provisioning/dashboards/signalchord.yml`, `infrastructure/monitoring/grafana/provisioning/dashboards/signalchord-overview.json`.
- CI validation: `scripts/validate_observability.py`.

Required dashboard panels cover API availability, pipeline freshness, Kafka consumer lag, notification delivery, telemetry export failures and event processing errors. Future production dashboards must add managed Kafka, PostgreSQL, Neo4j, Redis, object storage and OpenSearch provider metrics.

## Telemetry retention

- Raw traces: 7 days in staging, 14 days in production unless legal/privacy review requires shorter retention.
- Metrics: 30 days high resolution, 13 months downsampled for capacity trends.
- Application logs: 30 days searchable, 1 year archived for security/audit events.
- Incident evidence: retained with the incident record according to legal/privacy approval.

## Runbooks

Primary runbooks:

- `docs/runbooks/incident-response.md`
- `docs/runbooks/replay.md`
- `docs/runbooks/dependency-outage.md`
- `docs/runbooks/data-quality.md`
- `docs/runbooks/source-takedown.md`

## External evidence still required

Issue #28 must remain open until staging provides dashboard exports or screenshots, sample distributed traces, alert firing/resolution records, paging/routing configuration, telemetry-retention settings from the real provider and at least one completed incident or game-day exercise.
