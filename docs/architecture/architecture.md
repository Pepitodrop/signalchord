# SignalChord architecture

## Executive view

SignalChord turns permitted source documents into explainable, replayable intelligence. Kafka is the durable processing backbone; Neo4j is the relationship source of truth; PostgreSQL owns transactional product configuration; object storage owns permitted raw documents; OpenSearch owns full-text retrieval indexes.

The system uses a small number of domain-aligned services rather than one service per operation. Latency-sensitive collection and streaming gateways are Go. Semantic processing is typed Python. The Rails application owns identity, tenancy, billing, governance and user-authored product state. React and React Native consume versioned APIs and real-time events.

## Architectural invariants

1. Every externally derived assertion retains document, source, extractor and model provenance.
2. Source reports, model extractions, graph inferences and human verification are distinct states.
3. Kafka consumers are at-least-once and idempotent. Kafka transactions are used only for consume-transform-produce stages where they materially reduce ambiguity.
4. Event time is source publication/observation time when available; ingestion time is never substituted silently.
5. Low-confidence entity matches remain candidates; they are not silently merged.
6. Clients cannot submit arbitrary Cypher. Graph access uses approved, parameterized query templates.
7. Tenant identifiers are carried through API calls, events, graph elements, cache keys, object paths and audit records.
8. Velato execution is deterministic, resource-bounded and isolated from network, filesystem, shell and native-code access.

## C4 context

```mermaid
C4Context
  title SignalChord system context
  Person(analyst, "Analyst", "Monitors entities, investigates claims, configures alerts")
  Person(admin, "Workspace administrator", "Controls sources, policies, access and governance")
  System(signalchord, "SignalChord", "Real-time intelligence knowledge graph")
  System_Ext(sources, "Permitted public sources", "RSS, Atom, webhooks and licensed feeds")
  System_Ext(notifications, "Notification providers", "Push, email and outbound webhooks")
  Rel(analyst, signalchord, "Searches, investigates and receives alerts")
  Rel(admin, signalchord, "Configures tenants, sources and policies")
  Rel(sources, signalchord, "Publishes or exposes source documents")
  Rel(signalchord, notifications, "Requests delivery")
```

## C4 containers

```mermaid
C4Container
  title SignalChord container architecture
  Person(user, "Analyst")
  Container(web, "Web", "React/TypeScript", "Analyst workstation")
  Container(mobile, "Mobile", "Expo React Native/TypeScript", "Alert and mobile investigation client")
  Container(rails, "Control plane", "Ruby on Rails", "Identity, tenancy, source registry, watchlists, policies, audit and public API")
  Container(gateway, "Realtime gateway", "Go", "Tenant-aware SSE/WebSocket delivery")
  Container(ingestion, "Ingestion services", "Go", "Discover, fetch and normalize documents")
  Container(ai, "Intelligence services", "Python", "NLP, entity resolution, claim intelligence, graph analytics and Velato")
  Container(kafka, "Kafka", "KRaft + Schema Registry + Connect", "Durable event backbone")
  ContainerDb(pg, "PostgreSQL", "SQL", "Transactional product state and outbox")
  ContainerDb(graph, "Neo4j", "Cypher + GDS", "Temporal knowledge graph")
  ContainerDb(search, "OpenSearch", "Search index", "Full-text and filtered retrieval")
  ContainerDb(objects, "Object storage", "S3-compatible", "Raw permitted documents")
  Rel(user, web, "HTTPS")
  Rel(user, mobile, "HTTPS / push")
  Rel(web, rails, "REST")
  Rel(mobile, rails, "REST")
  Rel(web, gateway, "SSE/WebSocket")
  Rel(mobile, gateway, "SSE/WebSocket")
  Rel(rails, pg, "SQL")
  Rel(rails, kafka, "Transactional outbox events")
  Rel(ingestion, kafka, "Produces/consumes versioned events")
  Rel(ai, kafka, "Produces/consumes versioned events")
  Rel(kafka, graph, "Neo4j sink/source connectors")
  Rel(rails, graph, "Approved parameterized queries")
  Rel(rails, search, "Search API")
  Rel(ingestion, objects, "Writes immutable raw objects")
```

## Article-to-alert vertical slice

```mermaid
sequenceDiagram
  participant R as Rails source registry
  participant F as feed-collector
  participant K as Kafka
  participant D as document-fetcher
  participant N as stream-normalizer
  participant P as nlp-pipeline
  participant E as entity-resolution
  participant G as Neo4j sink
  participant V as velato-engine
  participant W as realtime-gateway
  R->>K: source.registered.v1 (outbox)
  F->>K: source.document.discovered.v1
  K->>D: discovered event
  D->>K: source.document.fetched.v1
  K->>N: fetched event
  N->>K: document.normalized.v1
  K->>P: document.nlp-requested.v1
  P->>K: document.nlp-completed.v1 + extracted events
  K->>E: entity.resolution-requested.v1
  E->>K: entity.resolved.v1
  K->>G: graph.mutation-requested.v1
  G->>K: graph.mutation-completed.v1 / CDC-selected graph change
  K->>V: alert.policy-evaluation-requested.v1
  V->>K: alert.created.v1
  K->>W: alert.created.v1
  W-->>W: tenant-aware fan-out
```

## Data ownership and consistency

| Store | Authoritative for | Reconciliation rule |
|---|---|---|
| PostgreSQL | users, organizations, workspaces, RBAC, sources, watchlists, policies, subscriptions, audit metadata | transactional outbox is replayed until acknowledged; no graph fact duplication |
| Kafka | ordered processing history within stable keys | schemas are backward compatible; consumer offsets can be reset from documented checkpoints |
| Object storage | immutable permitted raw document bytes and fetch metadata | key is tenant/source/content hash; deletion tombstone prevents re-ingestion |
| Neo4j | graph nodes, relationships, temporal validity, evidence links and graph-derived signals | mutations are idempotent `MERGE` operations keyed by stable IDs |
| OpenSearch | full-text/search projection | rebuilt from normalized documents and entity projections; never authoritative |
| Redis | ephemeral caches, rate limits and subscription state | disposable; no durable business state |

## Delivery semantics

- Discovery, fetch, extraction and graph mutation consumers are at-least-once with idempotency keys.
- Consume-transform-produce stages use Kafka transactions when both input offsets and output records can be committed atomically.
- External side effects use an inbox/idempotency ledger and retryable state machine.
- Late events are accepted within per-topic windows and marked with `lateness_ms`; graph mutations compare `observed_at` and `valid_from` before superseding state.
- Dead-letter records include original payload bytes, schema ID, exception class, stack fingerprint, attempts and replay eligibility.

## Multi-tenant model

All product-owned records contain `tenant_id`. Shared public entities may exist in a global canonical layer, but tenant-specific watchlists, investigations, annotations, alerts and private sources remain tenant scoped. The graph-query service injects tenant predicates and rejects templates without declared isolation rules.

## Operational deployment

Local development uses Docker Compose. Production uses Helm/Kubernetes with separate node pools for Kafka, Neo4j, stateful datastores and stateless services. Terraform provisions network, identities, secrets, object storage, managed DNS and optional managed Kafka/Neo4j equivalents.

## Unresolved architecture decisions

- Exact licensed-source mix and per-source retention constraints.
- Initial production NLP models and inference hosting strategy.
- Whether global canonical entities are enabled for all plans or enterprise-only.
- Push provider and mobile background-delivery limits.
- The supported Velato subset after compatibility testing against the original interpreter.
