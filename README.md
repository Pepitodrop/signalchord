# SignalChord

**Evidence-linked news intelligence built on Kafka and Neo4j.**

SignalChord is an early-stage, multi-tenant intelligence platform that ingests permitted news sources, preserves provenance, extracts entities and claims, projects them into a temporal knowledge graph, evaluates auditable alert policies, and delivers web, mobile and realtime experiences.

> **Project status:** public-alpha quality. The repository contains a tested reference vertical slice and production-oriented deployment scaffolding. It is not yet a production service or a finished commercial product. See [Production readiness](docs/production-readiness.md).

## What is implemented

The reference article-to-alert flow includes:

1. Go RSS/Atom discovery, fetching and normalization.
2. Kafka event contracts and versioned Protobuf schemas.
3. MinIO-backed immutable source storage and Redis deduplication.
4. Deterministic Python extraction, entity resolution and claim processing.
5. A first-party, idempotent Kafka-to-Neo4j graph projector.
6. OpenSearch projection, graph query and analytics APIs.
7. Rails identity, tenancy, RBAC, sources, watchlists, alerts and audit APIs.
8. Deterministic Velato-compatible policy evaluation.
9. React analyst UI, Expo mobile client and an authenticated realtime gateway.
10. Docker Compose integration tests and a consolidated Helm chart for stateless workloads.

The default verified path deliberately avoids requiring a third-party Kafka Connect plugin. Kafka Connect configuration remains available as an optional integration for environments that validate and operate it separately.

## Quick start

Requirements:

- a recent Docker Engine or Docker Desktop
- Docker Compose v2
- `curl`
- At least 12 GB of available container memory is recommended for the full profile

```bash
cp .env.example .env
./scripts/dev-up.sh
./scripts/smoke-test.sh
```

The smoke test exercises the synthetic repository-owned source through Kafka, object storage, NLP, Neo4j, OpenSearch, alert persistence and the web surface.

Development credentials and host port exposure in Compose are intentionally local-only.

## Deployment model

Source modules remain independently testable, but the initial Kubernetes topology groups processes that share scaling and release characteristics:

- control plane
- transactional outbox
- ingestion
- intelligence
- graph/search projection
- graph query
- graph analytics
- alerting and notifications
- realtime gateway
- web

Stateful infrastructure—Kafka, PostgreSQL, Neo4j, Redis, object storage and OpenSearch—is expected to be externally operated or managed in production. Docker Compose remains the local and CI reference runtime.

See [Deployment](docs/deployment.md) and the Helm chart under `infrastructure/kubernetes/helm/signalchord`.

## Repository map

- `apps/` — web, mobile and Rails control plane.
- `services/` — Go and Python streaming components.
- `packages/` — TypeScript clients, domain types and event schemas.
- `graph/` — Neo4j constraints, queries and fixtures.
- `connectors/` — optional connector configurations.
- `infrastructure/` — Docker, Kubernetes, Terraform and monitoring.
- `docs/` — architecture, ADRs, runbooks, governance and readiness.

## Architecture

Start with:

- [Architecture overview](docs/architecture/architecture.md)
- [Service responsibility matrix](docs/architecture/service-responsibility-matrix.md)
- [Kafka topic catalog](docs/architecture/kafka-topic-catalog.md)
- [Neo4j graph model](docs/architecture/neo4j-graph-model.md)
- [Production readiness](docs/production-readiness.md)

## Security and responsible use

Use only sources you are legally permitted to collect and process. Do not deploy the example credentials from Compose. Production deployment requires external secrets, TLS/SASL, least-privilege access, source licensing, retention controls, backup/restore testing and a documented incident process.

Report vulnerabilities according to [SECURITY.md](SECURITY.md). Data and source constraints are described in [Data governance](docs/data-governance.md) and the [Threat model](docs/threat-model.md).

## Publication status

The codebase is suitable to publish as an **alpha/open-development repository** once the pull request checks are green. Publication does not mean the hosted system is production-ready. Known operational and product gaps are listed explicitly in [Production readiness](docs/production-readiness.md).

## License

SignalChord source code is licensed under the [Apache License 2.0](LICENSE). Third-party services, images, connectors, datasets and model artifacts retain their own licenses and terms. See [NOTICE](NOTICE) and the [license notes](docs/license-recommendation.md).
