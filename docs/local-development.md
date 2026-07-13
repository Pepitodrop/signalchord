# Local development

## Requirements

Use a recent Docker Engine or Docker Desktop with Compose v2 and `curl`. At least 12 GB of available container memory is recommended for the full profile. No external source is required: the default slice uses a synthetic repository-owned RSS/article fixture.

## Start and verify

```bash
cp .env.example .env
./scripts/dev-up.sh
./scripts/smoke-test.sh
```

The reference profile starts Kafka in KRaft mode, Schema Registry, Neo4j Community, PostgreSQL, Redis, MinIO, OpenSearch, OpenTelemetry Collector, Prometheus, Grafana and all implemented application services.

Graph writes use the first-party `graph-projector`, which provides an allowlisted, idempotent and tested Kafka-to-Neo4j path.

## Optional Kafka Connect profile

Kafka Connect is not required for the verified local runtime. To test it independently:

```bash
docker compose --profile connect up -d --build kafka-connect
./scripts/configure-connectors.sh
```

Connector compatibility must be validated against the exact Kafka Connect, Neo4j and plugin versions before production use.

## Endpoints

- Web: `http://localhost:5173`
- Control-plane API: `http://localhost:3000`
- Realtime health: `http://localhost:8088/healthz`
- Schema Registry: `http://localhost:8081`
- Neo4j Browser: `http://localhost:7474`
- MinIO console: `http://localhost:9001`
- OpenSearch: `http://localhost:9200`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

All Compose credentials are development-only examples.

## Reset

```bash
./scripts/reset.sh
```

## Troubleshooting

- Kafka not healthy: inspect `docker compose logs kafka` and verify port `29092` is free.
- No alert: inspect `document-fetcher`, `stream-normalizer`, `nlp-worker`, `velato-worker` and `alert-projector` in order.
- No graph node: inspect `graph-projector` and `graph.mutation-requested.v1.dlq`.
- Low-memory host: stop OpenSearch and Grafana first or increase Docker memory.
