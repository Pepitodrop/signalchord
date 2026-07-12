# Service responsibility matrix

| Component | Language | Owns | Consumes | Produces | Durable state |
|---|---|---|---|---|---|
| feed-collector | Go | RSS/Atom polling, webhook intake, adapter policy, rate limiting | source.registered, source.poll.requested | source.document.discovered | Redis rate-limit state only |
| document-fetcher | Go | permitted fetch, HTTP metadata, charset normalization, hashing, raw upload | source.document.discovered | source.document.fetched | object storage + inbox ledger |
| stream-normalizer | Go | canonical URL, timestamp normalization, exact/near duplicate routing, schema validation | source.document.fetched | document.normalized, duplicate-detected, nlp-requested | compacted dedupe keys |
| realtime-gateway | Go | tenant subscription authorization and SSE/WebSocket fan-out | alert.created, graph mutation completed | delivery telemetry | Redis ephemeral subscriptions |
| nlp-pipeline | Python | cleanup, language, NER, claims, relations, topics, embeddings | document.nlp-requested | nlp-completed, mention/claim/relationship extracted | model metadata only |
| entity-resolution | Python | deterministic + embedding candidate matching | entity.resolution-requested | entity.resolved | optional vector index projection |
| claim-intelligence | Python | claim clustering, corroboration, contradiction and evolution | claim.extracted, entity.resolved | claim.clustered, contradiction-detected | derived model state via graph |
| graph-analytics | Python | centrality, communities, emerging clusters and explainable evidence | graph.analytics-requested, graph CDC | intelligence.signal-created | Neo4j GDS projections |
| velato-engine | Python | MIDI parsing, constrained IR, deterministic sandbox and simulation | policy evaluation requested | alert.created or evaluation result | versioned program/result metadata in Rails |
| control-plane | Ruby/Rails | identity, tenancy, RBAC, sources, watchlists, policies, reviews, billing, audit, public API | notifications and selected status events | outbox domain events | PostgreSQL |
| web | React/TypeScript | analyst desktop UX | REST + realtime | user commands | browser cache only |
| mobile | Expo/TypeScript | mobile alerts and compact investigation UX | REST + push/realtime | user commands | encrypted token + offline cache |
| graph-query | Rails module initially; separable later | approved Cypher templates, tenant injection, query budgets | API requests | query responses and audit | none |
