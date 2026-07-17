# SignalChord

**Evidence-linked news intelligence built on Kafka and Neo4j.**

SignalChord is an early-stage, multi-tenant intelligence platform that ingests permitted news sources, preserves provenance, extracts entities and claims, projects them into a temporal knowledge graph, evaluates auditable alert policies, and delivers web, mobile and realtime experiences.

> **Project status:** verified public-alpha quality. The repository contains a tested reference vertical slice and a single-owner k3s deployment package. It is not a highly available internet service or a finished commercial product. See [Production readiness](docs/production-readiness.md).

## What is implemented

The reference article-to-alert flow includes:

1. Go RSS/Atom discovery, fetching and normalization.
2. Kafka event contracts and versioned Protobuf schemas.
3. MinIO-backed immutable source storage and Valkey deduplication.
4. Deterministic Python extraction, entity resolution and claim processing.
5. A first-party, idempotent Kafka-to-Neo4j graph projector.
6. OpenSearch projection, graph query and analytics APIs.
7. Rails identity, tenancy, RBAC, sources, watchlists, alerts and audit APIs.
8. Deterministic Velato-compatible policy evaluation.
9. React analyst UI, Expo mobile client and an authenticated realtime gateway.
10. Docker Compose integration tests and Helm charts for the application and a single-server community stack.

The verified path uses its own graph projector and versioned Protobuf contracts. It does not require Confluent Schema Registry, Kafka Connect, a proprietary LLM API, or another paid hosted service.

## Community self-hosting profile

The local and single-server reference stacks are designed to run entirely with self-hosted community software:

- Apache Kafka
- PostgreSQL
- Neo4j Community Edition
- Valkey
- MinIO
- OpenSearch
- OpenTelemetry Collector
- Prometheus
- Grafana OSS

No licence fee or paid API subscription is required to run the repository-owned reference flow. Running it still consumes your own machine or server resources, and optional external services such as domains, email delivery, mobile stores, managed databases or cloud hosting can cost money. See [Community self-hosting](docs/community-self-hosting.md).

## Languages and what they do

| Language or format | Role in SignalChord |
| --- | --- |
| **TypeScript / TSX** | Implements the React analyst web application, Expo mobile client, shared API clients and domain types. |
| **Go** | Runs the high-throughput ingestion path: feed collection, document fetching, stream normalization and the authenticated realtime gateway. |
| **Python** | Implements NLP extraction, entity resolution, claim intelligence, graph and search projection, graph query and analytics services, alert and notification workers, and the Velato policy engine. |
| **[Velato](https://velato.net/)** | Encodes executable alert policies as musical MIDI instruction sequences. SignalChord also provides auditable `.vasm` source that compiles to the same deterministic MIDI policy IR. |
| **Ruby** | Powers the Rails control plane for identity, organizations, tenancy, RBAC, sources, watchlists, investigations, alerts, audit records and the transactional outbox. |
| **Protocol Buffers** | Defines versioned Kafka event contracts and compatibility-safe schemas shared across services. |
| **Cypher** | Defines Neo4j constraints, idempotent graph mutations, evidence relationships and approved graph queries. |
| **SQL** | Backs the PostgreSQL control-plane data model through Rails migrations and Active Record. |
| **Shell** | Automates local startup, dependency initialization, schema setup, smoke tests, backup, restore, acceptance and operational workflows. |
| **YAML** | Configures Docker Compose, Kubernetes and Helm, GitHub Actions, observability and service deployment settings. |
| **HCL / Terraform** | Describes infrastructure provisioning wrappers and environment-level deployment inputs. |
| **Dockerfile and nginx configuration** | Build reproducible service images and serve the web application through a rootless runtime with same-origin API and realtime proxying. |

## Velato policy programming

SignalChord uses a deliberately constrained Velato dialect for policies that must be understandable as code, playable as MIDI and safe to execute in an alerting pipeline.

Its main features are:

1. **MIDI-native executable source:** pitch intervals encode operations, MIDI channels select instruction banks and bounded note velocity values encode operands.
2. **Deterministic auditability:** MIDI and `.vasm` source compile into the same sealed stack-machine IR with static analysis, source/IR hashes and reproducible execution traces.
3. **Functional policy outputs:** programs calculate `alert_score`, `severity_code`, `routing_code` and `suppressed`; they cannot access the filesystem, network or shell and cannot create unbounded loops.

Five checked-in musical programs provide distinct production functions:

| Program | Musical direction | Function in SignalChord |
| --- | --- | --- |
| [`Watchlist Privateer`](velato/programs/watchlist-privateer.vasm) | Original cinematic seafaring action pulse | Escalates corroborated, recent watchlist stories to urgent routing code `7` and suppresses low-trust or heavily contradicted material. |
| [`City Waltz`](velato/programs/city-waltz.vasm) | Original modern German indie-pop waltz pulse | Prioritizes geographically relevant and well-sourced stories for local-impact routing code `4`. |
| [`Contradiction Canon`](velato/programs/contradiction-canon.vasm) | Original interlocking canon-like figures | Detects contradiction-heavy stories and routes them to investigation code `5`. |
| [`Source Trust Nocturne`](velato/programs/source-trust-nocturne.vasm) | Original restrained nocturne contour | Operates as a source-quality gate and routes highly trusted material to code `2`. |
| [`Novelty Rondo`](velato/programs/novelty-rondo.vasm) | Original returning novelty-recency motif | Finds emerging stories and routes strong discoveries to code `3`. |

The two requested stylistic showcase pieces use broad genre characteristics only and do not reproduce an existing song's melody, harmony or arrangement. Every program is tested by compiling its assembly to MIDI, decoding the MIDI back to IR and executing it against representative SignalChord inputs. See [Velato MIDI policies](velato/programs/README.md).

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

The repository includes a single-owner, single-node k3s profile for Kafka, PostgreSQL, Neo4j Community, Valkey, MinIO, OpenSearch and observability. It uses digest-pinned application images, ClusterIP-only stateful services, restricted pod security, trusted TLS ingress, encrypted backup, checksum-verified restore and a live article-to-alert acceptance command. It is not highly available and its internal dependency transport is plaintext inside the documented one-node trust boundary.

See [Single-server Kubernetes](docs/single-server-kubernetes.md), [Deployment](docs/deployment.md), and the Helm charts under `infrastructure/kubernetes/helm`.

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

Use only sources you are legally permitted to collect and process. Do not deploy the example credentials from Compose. Internet deployment requires unique runtime secrets, trusted TLS, least-privilege access, source licensing, retention controls, tested backup/restore and a documented incident process. The v1 single-server profile is not a multi-operator production security boundary.

Report vulnerabilities according to [SECURITY.md](SECURITY.md). Data and source constraints are described in [Data governance](docs/data-governance.md) and the [Threat model](docs/threat-model.md).

## Publication status

The repository has automated public-source governance and a complete-history secret/proprietary-content gate. Change visibility from private to public only after `Repository History Audit`, full CI, workflow security, source snapshot, publication readiness and single-server k3s checks pass on the exact commit, and the manual GitHub settings in the [publication checklist](docs/publication-checklist.md) are complete.

Making the source public does not mean a hosted SignalChord deployment is production-ready. Before processing real customer data, complete the operational, legal, security and reliability gates documented in [Production readiness](docs/production-readiness.md).

## License

SignalChord source code is licensed under the [Apache License 2.0](LICENSE). Third-party services, images, connectors, datasets and model artifacts retain their own licenses and terms. See [NOTICE](NOTICE), [Community self-hosting](docs/community-self-hosting.md), and the [license notes](docs/license-recommendation.md).
