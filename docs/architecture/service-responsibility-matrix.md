# Service responsibility matrix

Source modules are independently testable. The initial Kubernetes deployment groups compatible processes into a smaller number of operational units; the `Deployment unit` column describes that initial topology.

| Component | Language | Owns | Consumes | Produces | Durable state | Deployment unit |
|---|---|---|---|---|---|---|
| feed-collector | Go | RSS/Atom polling, source-policy checks and discovery | source registry/API state | source.document.discovered | none | CronJob |
| document-fetcher | Go | permitted fetch, HTTP validation, hashing and immutable upload | source.document.discovered | source.document.fetched | object storage | ingestion |
| stream-normalizer | Go | canonical URL, timestamp normalization and exact deduplication | source.document.fetched | document.normalized, document.nlp-requested | compacted Redis keys | ingestion |
| nlp-pipeline | Python | cleanup, language, entities, claims, relations, topics and deterministic embeddings | document.nlp-requested | extraction events, graph mutations, policy requests | model metadata only | intelligence |
| entity-resolution | Python | deterministic canonical entity matching | entity.mention-extracted, relationship.extracted | entity.resolved, graph mutations | graph projection only | intelligence |
| claim-intelligence | Python | claim normalization and clustering | claim.extracted | claim.clustered, graph mutations | graph projection only | intelligence |
| graph-projector | Python | allowlisted, idempotent mutation projection into Neo4j | graph.mutation-requested | graph.mutation-completed, mutation DLQ | Neo4j | projection |
| search-projector | Python | rebuildable document/entity search indexes | normalized and resolved events | projection telemetry | OpenSearch projection | projection |
| graph-query | Python/FastAPI | approved Cypher templates and query budgets | authenticated API requests | query responses | none | graph-query |
| graph-analytics | Python | centrality, communities and explainable signals | graph events and API requests | intelligence signals and API responses | Neo4j GDS projections | graph-analytics |
| velato-engine | Python | constrained MIDI policy parsing, simulation and evaluation | policy evaluation requests | alert.created or evaluation result | policy/result metadata in Rails | alerting |
| alert-projector | Python | durable alert projection | alert.created | control-plane alert writes | PostgreSQL via control-plane | alerting |
| notification-worker | Python | idempotent outbound delivery | notification requests | delivery results | delivery ledger via control-plane | alerting |
| control-plane | Ruby/Rails | identity, tenancy, RBAC, sources, watchlists, policies, reviews, billing and audit | API commands and selected status events | transactional outbox events | PostgreSQL | control-plane |
| outbox-publisher | Ruby | reliable PostgreSQL-to-Kafka publication | pending outbox rows | domain events | PostgreSQL outbox | outbox |
| realtime-gateway | Go | tenant authorization and bounded SSE fan-out | alert.created and selected status events | delivery telemetry | Redis ephemeral state | realtime |
| web | React/TypeScript | analyst desktop UX | REST and realtime | user commands | browser cache only | web |
| mobile | Expo/TypeScript | compact alert/investigation UX | REST, push and realtime | user commands | encrypted token/cache | distributed client |

Kafka Connect templates remain optional interoperability assets. They are not part of the required local or initial production runtime; environments choosing them must validate the exact connector and Neo4j versions independently.
