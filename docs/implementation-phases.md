# Implementation phases and gates

The system is delivered as one coherent article-to-alert path before breadth is added. Every stage runs tests, linters, type checks, smoke tests and documentation updates.

## Phase 0 — Architecture and repository foundation

Deliver architecture, ADRs, schemas, graph model, monorepo, CI, local infrastructure, threat model and roadmap.

**Gate:** repository conventions are reviewable; schema compatibility and static checks run in CI; no secrets are committed.

## Phase 1 — Infrastructure and health

Start Kafka KRaft, Schema Registry, Neo4j, PostgreSQL, Redis, MinIO, OpenSearch, OpenTelemetry Collector, Prometheus and Grafana with health checks and seed scripts. Kafka Connect remains an optional compatibility profile.

**Gate:** one command starts and resets the platform; topic and datastore health are verified.

## Phase 2 — Article-to-graph vertical slice

A permitted sample RSS article is discovered by Go, fetched and stored, normalized, sent through typed Python NLP, resolved, converted into idempotent Neo4j mutations and inspected through evidence-linked queries.

**Gate:** one correlation ID traces discovery through graph persistence; duplicate replay produces no duplicate graph facts.

## Phase 3 — Rails source and watchlist control plane

Implement Rails 8 application foundations, organizations/workspaces, RBAC, source policy metadata, watchlists, API tokens, audit logs and transactional outbox publisher.

**Gate:** an authorized tenant registers a source and watchlist; outbox events publish exactly once from the application perspective and are safely replayable.

## Phase 4 — Analyst web visualization

Connect React search, entity page, timeline, evidence panel and bounded graph explorer to versioned APIs.

**Gate:** an analyst can inspect the sample article, entity, claim, relationship and every supporting evidence span without direct Cypher.

## Phase 5 — Velato policy evaluation

Finalize supported Velato MIDI subset, constrained IR, deterministic worker sandbox, default MIDI programs, fallback engine, simulation API and audit storage.

**Gate:** a default MIDI policy creates an explainable alert; unsupported, oversized, malicious and nondeterministic inputs are rejected by tests.

## Phase 6 — Real-time alerts

Connect policy output to Kafka, Rails alert projection and tenant-authorized Go SSE/WebSocket gateway.

**Gate:** a web client receives a durable alert and can trace it to policy inputs, graph path and source evidence.

## Phase 7 — Mobile alert experience

Implement Expo authentication, secure token storage, alert feed, deep links, entity timeline, simplified graph, push and bounded offline cache.

**Gate:** iOS and Android smoke tests open the sample alert from a deep link and retain recently viewed evidence offline.

## Phase 8 — Intelligence expansion

Add production NLP adapters, claim clustering, contradiction evaluation, embeddings, source diversity, GDS analytics and review tooling.

**Gate:** fixture precision/recall thresholds, calibration and explainability requirements are met.

## Phase 9 — Hardening and beta

Run tenant isolation, load, replay, failure recovery, backup/restore, source deletion, licensing and closed-design-partner tests.

**Gate:** launch blockers are resolved and operational ownership, SLOs, recovery objectives and rights metadata are approved.

## Current state

The foundation branch contains the executable Rails control plane, Go ingestion/realtime services, deterministic Python intelligence workers, the first-party Neo4j graph projector, web/mobile clients, Docker Compose integration runtime and a consolidated Helm scaffold for stateless workloads.

The repository remains public-alpha rather than production-approved. Production NLP evaluation, licensed source onboarding, immutable supply-chain promotion, external secrets/TLS, backup and restore drills, realistic load/failure testing, signed mobile delivery and final operational ownership remain gated work. See `docs/production-readiness.md`.
