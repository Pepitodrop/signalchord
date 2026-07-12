# Repository tree

```text
signalchord/
├── apps/
│   ├── web/                         # React/TypeScript analyst application
│   ├── mobile/                      # Expo React Native client
│   └── control-plane/               # Rails transactional product boundary
├── services/
│   ├── feed-collector/              # Go RSS/Atom discovery
│   ├── document-fetcher/            # Go permitted HTTP fetch and raw storage
│   ├── stream-normalizer/           # Go normalization and deduplication
│   ├── realtime-gateway/            # Go tenant-aware SSE delivery
│   ├── nlp-pipeline/                # Python extraction pipeline
│   ├── entity-resolution/           # Python canonical entity matching
│   ├── claim-intelligence/          # Python claim normalization/clustering
│   ├── graph-projector/             # Python allowlisted Neo4j mutation sink
│   ├── graph-query/                 # Python approved graph query API
│   ├── graph-analytics/             # Python graph analytics API/worker
│   ├── search-projector/            # Python OpenSearch projection
│   ├── alert-projector/             # Python durable alert projection
│   ├── notification-worker/         # Python idempotent notification delivery
│   ├── velato-engine/               # Python constrained MIDI policy runtime
│   ├── internal/                    # Go shared libraries
│   └── python_common/               # Python shared models
├── packages/
│   ├── event-schemas/               # Protobuf contracts and compatibility policy
│   ├── domain-types/                # Shared TypeScript domain contracts
│   └── api-client/                  # TypeScript API client
├── connectors/                      # Optional Kafka Connect templates
├── graph/                           # Neo4j migrations, queries and fixtures
├── velato/                          # Policy programs and specification
├── infrastructure/
│   ├── docker/                      # Application image definitions
│   ├── kubernetes/                  # Consolidated Helm deployment scaffold
│   ├── terraform/                   # Infrastructure integration skeleton
│   └── monitoring/                  # OTel, Prometheus and Grafana config
├── docs/                            # Architecture, runbooks and readiness
├── scripts/                         # Local bootstrap, smoke and reset workflows
└── .github/workflows/               # CI and source snapshots
```

Generated build output, secrets, raw source documents and model artifacts are not committed. The current implementation and remaining production gates are documented in `README.md` and `docs/production-readiness.md`.
