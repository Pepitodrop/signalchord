# Capacity, Load, and Cost Plan

SignalChord is not production-capacity approved until the scenario in `load/scenarios/signalchord-capacity-v1.json` has been run against a staging-like environment with managed dependencies, representative network policy, production TLS, production-like persistence settings, and legally permitted fixtures.

## Workload Profiles

The versioned scenario defines three mandatory profiles:

- `expected`: steady-state public-alpha traffic for ingestion, query APIs, realtime subscribers, and notification fan-out.
- `burst`: short source or customer spikes that should recover without unacceptable Kafka lag, queue age, or alert latency.
- `degraded-dependency`: expected traffic while OpenSearch, Neo4j, or the notification provider is slow or rate-limiting.

Fixtures must be synthetic or licensed. Do not use customer data, production exports, unlicensed source documents, private credentials, or proprietary model weights in load tests.

## Regression Gates

Load runs must emit JSON matching the scenario result contract. `scripts/validate_capacity.py` compares observed metrics with journey thresholds and fails when p95 latency, error rate, Kafka lag, queue age, CPU saturation, or memory saturation exceeds the agreed limit.

The repository includes `load/results/repository-smoke.json` only to prove the contract and validator in CI. It is not evidence for production capacity.

## Runtime Controls

The first production-facing limits under test are:

- `API_RATE_LIMIT=600` API requests per IP per minute.
- `AUTH_RATE_LIMIT=30` auth attempts per IP per 5 minutes.
- `API_MAX_BODY_BYTES=1048576`.
- Ingress body size `1m`, proxy read timeout `3600s`, send timeout `60s`, and connect timeout `5s`.
- Worker HTTP timeouts documented in the scenario for fetch, search proxy, notification, and policy calls.

Ingress, CDN, WAF, and load-balancer settings must be checked in the deployed environment to prove they match or are stricter than application limits.

## Kafka and Autoscaling

The scenario records initial partition assumptions for article, graph, alert, and notification topics. Consumer replicas must not exceed topic partitions for the relevant consumer group. Increase partitions only with replay-order review, lag measurements, and rollback notes.

CPU alone is not an acceptable autoscaling signal for Kafka-backed workers. Autoscaling must be based on a combination of consumer lag, queue age, processing latency, HTTP p95 latency, CPU saturation, and memory saturation. Helm autoscaling remains disabled until staging measurements support concrete min/max replica settings.

## Capacity and Cost Envelope

The initial realistic deployment size to measure is:

| Area | Starting point | Evidence required before approval |
| --- | --- | --- |
| Stateless workloads | Helm defaults in `values.yaml` with production overrides | CPU, memory, restart, p95 latency, and queue-age results for all profiles |
| Kafka | Scenario partition counts | Lag, throughput, replay, and degraded-consumer recovery evidence |
| PostgreSQL | Managed instance with connection limits and backups | query p95, connection saturation, migration timing, and restore evidence |
| Neo4j | Managed or dedicated graph service | write/query p95, index coverage, memory/page-cache saturation |
| OpenSearch | Managed or dedicated domain | index/query p95, shard/index sizing, refresh behavior under burst |
| Object storage | Managed bucket with tenant prefixes | request rate, error rate, lifecycle and retention policy evidence |

Cost approval requires a provider-specific bill of materials for the measured environment, monthly steady-state cost, burst cost, per-document estimate, and per-tenant estimate. Repository code can define the model inputs, but finance or business approval must remain external evidence.

## Required Evidence

Attach the following to issue #27 before closure:

- raw JSON load results for all three profiles;
- scenario command line, git SHA, image digests, and environment configuration;
- dashboard exports or screenshots for latency, lag, queue age, saturation, and dependency health;
- Kafka partition and consumer group lag analysis;
- PostgreSQL, Neo4j, and OpenSearch index/resource analysis;
- Kubernetes resource, autoscaling, and quota updates justified by measurements;
- approved infrastructure and per-document/per-tenant cost model.
