# Repository tree

```text
signalchord/
├── apps/
│   ├── web/                         # React/TypeScript analyst application
│   ├── mobile/                      # Expo React Native application
│   └── control-plane/               # Rails transactional product boundary
├── services/
│   ├── feed-collector/              # Go RSS/Atom and webhook discovery
│   ├── document-fetcher/            # Go permitted HTTP fetch and raw storage
│   ├── stream-normalizer/           # Go normalization, dedupe and DLQ routing
│   ├── realtime-gateway/            # Go tenant-aware SSE/WebSocket delivery
│   ├── nlp-pipeline/                # Python extraction pipeline
│   ├── entity-resolution/           # Python canonical entity matching
│   ├── claim-intelligence/          # Python claim grouping and contradiction
│   ├── graph-analytics/             # Python Neo4j GDS analytics
│   ├── velato-engine/               # Python constrained MIDI policy runtime
│   ├── internal/                    # Go shared libraries
│   └── python_common/               # Python shared models
├── packages/
│   ├── event-schemas/               # Protobuf and schema compatibility policy
│   ├── domain-types/                # Shared TypeScript domain contracts
│   ├── api-client/                  # Generated and handwritten API clients
│   ├── ui/                          # Accessible shared React primitives
│   ├── observability/               # Shared telemetry conventions
│   └── test-fixtures/               # Cross-language deterministic fixtures
├── connectors/
│   ├── neo4j-sink/                  # Kafka-to-Neo4j mutations
│   └── neo4j-source/                # Selected Neo4j CDC projections
├── graph/
│   ├── schema/
│   ├── migrations/
│   ├── queries/
│   └── fixtures/
├── velato/
│   ├── programs/
│   ├── midi-fixtures/
│   └── policy-spec/
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   ├── terraform/
│   └── monitoring/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── api/
│   ├── runbooks/
│   ├── business-case.md
│   ├── clickup-roadmap.md
│   ├── threat-model.md
│   └── data-governance.md
├── scripts/
└── .github/workflows/
```

Directories that are not yet executable contain a README defining ownership and their stage gate. Generated bindings, model artifacts, secrets and source documents are never committed.
