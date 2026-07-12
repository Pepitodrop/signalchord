# SignalChord

**Real-time intelligence from connected news signals.**

SignalChord is a production-oriented, multi-tenant news intelligence platform built around Apache Kafka and Neo4j. It ingests permitted public information, preserves source provenance, extracts entities and claims, builds a temporal knowledge graph, evaluates auditable alert policies—including constrained Velato MIDI programs—and delivers real-time web and mobile experiences.

## Current delivery stage

This branch implements the foundation and the first coherent vertical-slice skeleton:

1. RSS/Atom discovery in Go.
2. Kafka event envelopes with versioned Protobuf schemas.
3. Document normalization and object-storage contracts.
4. Typed Python NLP, entity-resolution and Velato policy services.
5. Idempotent Neo4j mutation contracts and schema scripts.
6. Rails control-plane boundary and outbox design.
7. React analyst UI and Expo mobile alert client.
8. Local Kafka KRaft, Schema Registry, Kafka Connect, Neo4j, PostgreSQL, Redis, MinIO, OpenSearch and observability stack.

The first slice is deliberately narrow. It proves the article-to-alert lifecycle before adding broad source coverage, advanced extraction models or large-scale graph analytics.

## Quick start

```bash
cp .env.example .env
./scripts/dev-up.sh
./scripts/smoke-test.sh
```

Requirements: Docker 26+, Docker Compose v2, 12 GB available RAM recommended.

## Repository map

- `apps/` — product surfaces and Rails control plane.
- `services/` — Kafka-oriented Go and Python bounded contexts.
- `packages/` — shared TypeScript types, clients, UI and event contracts.
- `graph/` — Neo4j schema, migrations, queries and fixtures.
- `connectors/` — Kafka Connect configurations.
- `infrastructure/` — Docker, Kubernetes, Terraform and monitoring.
- `docs/` — architecture, ADRs, runbooks, roadmap, governance and business case.

## Architecture

Start with [`docs/architecture/architecture.md`](docs/architecture/architecture.md), then review the [topic catalog](docs/architecture/kafka-topic-catalog.md), [graph model](docs/architecture/neo4j-graph-model.md), and [implementation phases](docs/implementation-phases.md).

## Status and honesty

This is an initial production-oriented foundation, not a completed commercial platform. The repository separates implemented vertical-slice code from planned service contracts. Completion criteria and unresolved risks are tracked in `docs/implementation-phases.md` and ClickUp import artifacts.

## License

Apache-2.0 is recommended for the platform code. Source adapters, model artifacts and third-party datasets may require narrower terms; see `docs/license-recommendation.md`.
