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
9. A browser-local [Merzato](https://github.com/Pepitodrop/merzato-lang) Policy Studio with five bounded features: Assembly execution, executable Piet/SVG artwork compilation, alert triage scoring, watchlist routing and contradiction suppression.
10. An authenticated Live Intelligence Lab with tenant-scoped graph growth, an API-observed Kafka workflow pulse, real `.merz` speech programs and a functional one-minute Velato score.
11. React analyst UI, Expo mobile client and an authenticated realtime gateway.
12. Docker Compose integration tests and Helm charts for the application and a single-server community stack.

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
| **[Merzato](https://github.com/Pepitodrop/merzato-lang)** | Provides a multimodal policy language in Policy Studio. Stable Assembly and Piet/MIDI artwork remain available, while Merzato 1.3 speech programs now implement alert triage, watchlist routing and contradiction suppression through the bounded local VM. |
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

Six checked-in musical programs provide distinct production functions:

| Program | Musical direction | Function in SignalChord |
| --- | --- | --- |
| [`Watchlist Privateer`](velato/programs/watchlist-privateer.vasm) | Original cinematic seafaring action pulse | Escalates corroborated, recent watchlist stories to urgent routing code `7` and suppresses low-trust or heavily contradicted material. |
| [`City Waltz`](velato/programs/city-waltz.vasm) | Original modern German indie-pop waltz pulse | Prioritizes geographically relevant and well-sourced stories for local-impact routing code `4`. |
| [`Contradiction Canon`](velato/programs/contradiction-canon.vasm) | Original interlocking canon-like figures | Detects contradiction-heavy stories and routes them to investigation code `5`. |
| [`Source Trust Nocturne`](velato/programs/source-trust-nocturne.vasm) | Original restrained nocturne contour | Operates as a source-quality gate and routes highly trusted material to code `2`. |
| [`Novelty Rondo`](velato/programs/novelty-rondo.vasm) | Original returning novelty-recency motif | Finds emerging stories and routes strong discoveries to code `3`. |
| [`Live Graph Minute`](velato/programs/live-graph-minute.vasm) | Original 100-instruction graph pulse at 100 BPM | Calculates graph momentum, derives severity, routes mature graph signals to code `6` and suppresses low-trust or contradiction-heavy material. |

The two requested stylistic showcase pieces use broad genre characteristics only and do not reproduce an existing song's melody, harmony or arrangement. Every program is tested by compiling its assembly to MIDI, decoding the MIDI back to IR and executing it against representative SignalChord inputs. `Live Graph Minute` additionally has an exact 100-instruction test and an approximately one-minute browser performance. See [Velato MIDI policies](velato/programs/README.md).

## Merzato multimodal policy programming

SignalChord integrates [Merzato 1.3.0](https://github.com/Pepitodrop/merzato-lang) in Policy Studio using selected upstream assembler, validator, error and speech-compiler modules pinned to commit `79d4a04ccc2836fb0caaa1254d5b03aeb2a02b19`. The browser uses a SignalChord-owned restricted execution adapter rather than Merzato's general browser host, so programs cannot obtain network, prompt, DOM, filesystem or shell capabilities.

Five Merzato features are available:

1. **Bounded Assembly policy runner:** write or paste `.mza` programs, validate opcodes, constants, labels, registers, operands and jump targets, execute them with strict step/stack/call-stack/heap/string limits, and inspect output, registers and the sealed instruction stream.
2. **Executable artwork compiler:** write ordered SVG rectangles using Piet colours plus `data-note` MIDI metadata; SignalChord compiles their colour transitions and note intervals into validated Merzato Assembly, runs the program locally, and displays the score, generated Assembly and final IR for auditing.
3. **Alert triage scoring:** a Merzato `.merz` speech program combines source trust, novelty, entity relevance, recency, source diversity, corroborations, contradictions and watchlist state into `alert_score`, `severity_code` and `routing_code` outputs.
4. **Watchlist routing:** a separate executable Merzato speech policy routes matched entities to urgent code `7`, regional code `4` or observation code `1`; unmatched signals are deterministically suppressed.
5. **Contradiction safety gate:** a third Merzato speech policy suppresses contradiction-dominated or low-trust signals and sends them to investigation route `5` while allowing stronger evidence through route `2`.

The three SignalChord decision programs compile their bounded inputs into immutable Merzato constants and expose the shared policy contract through VM registers: `r10` is `alert_score`, `r11` is `severity_code`, `r12` is `routing_code` and `r13` is `suppressed`. Their generated Assembly and validated instruction streams remain visible in Policy Studio for auditability.

Two additional checked-in speech examples demonstrate the actual `.merz` profile: [`meme-cabinet.merz`](apps/web/public/programs/merz/meme-cabinet.merz) uses every documented meme alias or marker, arithmetic, registers, conditional control flow and a callable `helfer` function; [`graph-growth-briefing.merz`](apps/web/public/programs/merz/graph-growth-briefing.merz) calculates a safe aggregate graph-momentum score through a callable `graph_score` function. These are fictional satire programs, not quotation or impersonation claims.

Only two local MerzScript phrases are enabled: `THE CRITIC SAYS` writes to the studio output and `THE PERFORMANCE IS OVER` halts execution. All other host phrases fail closed. Vendored source provenance and the MIT licence are retained under [`apps/web/src/vendor/merzato-lang`](apps/web/src/vendor/merzato-lang).

## Live Intelligence Lab

After signing in, open `/lab.html` or select **Live Lab** in the web interface. The lab visualizes the authenticated tenant's graph projection and API-observed article-to-alert progress, displays graph growth over time, listens to the existing authenticated realtime stream and exposes the creative Merzato and Velato sources.

The lab does not connect directly to Neo4j or Kafka. It does not expose database or broker credentials, raw Kafka payloads, consumer-group administration, complete graph properties or cross-tenant data. See [Live Intelligence Lab](docs/live-intelligence-lab.md).

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
- `apps/web/src/vendor/merzato-lang/` — pinned Merzato assembler, validator, error and speech-compiler source plus the MIT licence used by Policy Studio.
- `apps/web/src/merzatoCorePolicies.ts` — three bounded Merzato speech programs for triage, routing and contradiction gating.
- `apps/web/public/programs/` — downloadable real `.merz` examples and the public mirror of the one-minute Velato source.
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

SignalChord source code is licensed under the [Apache License 2.0](LICENSE). The vendored Merzato assembler, validator, error and speech-compiler modules remain under their included MIT licence. Third-party services, images, connectors, datasets and model artifacts retain their own licenses and terms. See [NOTICE](NOTICE), [Community self-hosting](docs/community-self-hosting.md), and the [license notes](docs/license-recommendation.md).
