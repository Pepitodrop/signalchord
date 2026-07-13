# Observability specification

All services emit OpenTelemetry traces, metrics and structured logs with `tenant_id` only where access-controlled, plus `event_id`, `event_type`, `correlation_id`, `causation_id`, `processing_stage`, service/version and replay ID.

## Required dashboards

| Dashboard | Primary signals |
|---|---|
| Kafka flow | records/sec per topic, produce latency/error, consumer lag, rebalance, partition skew |
| Processing | end-to-end event-time latency, stage latency, retries, DLQ rate, late/out-of-order count |
| NLP quality | request latency/error, model/version volume, entities/claims per document, evaluation precision and calibration |
| Entity resolution | accepted/candidate/review rates, score distribution, merge/unmerge and precision fixtures |
| Neo4j | mutation latency/error, transaction retries, query latency by approved template, page cache and connector failures |
| Policy engine | evaluations/sec, execution latency, instruction count, rejection reason, fallback use and output distribution |
| Realtime/API | active SSE/WebSocket connections, dropped slow-subscriber messages, API latency/error/rate-limit and auth denial |
| Tenant usage | sources, documents, graph mutations, searches, alerts, exports and metered limits without leaking content |

## SLO starting points

These are internal initial targets, not customer commitments: 99.9% control-plane API availability; 95% of permitted feed articles available in the graph within five minutes; 99% of high-severity alerts delivered to the durable inbox within one minute after policy request; zero cross-tenant result leakage.

## Alerting

Page on tenant-isolation violations, secret/auth anomalies, sustained broker unavailability, data-loss risk, runaway notification delivery and backup failure. Ticket or notify for lag growth, DLQ increases, model-quality regression, connector restart loops, query-budget rejection changes and cost anomalies.
