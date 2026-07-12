# Local development

## Requirements

Docker Engine 26 or Docker Desktop with Compose v2, `curl`, and approximately 12 GB available RAM. No external source is required: the default slice uses a synthetic, repository-owned RSS/article fixture.

## Start

```bash
cp .env.example .env
./scripts/dev-up.sh
./scripts/smoke-test.sh
```

The script starts Kafka in KRaft mode, Schema Registry, Kafka Connect with Neo4j Connector 5.5.0, Neo4j Community, PostgreSQL, Redis, MinIO, OpenSearch, OpenTelemetry Collector, Prometheus, Grafana and the implemented slice services.

## Endpoints

- Web: `http://localhost:5173`
- Realtime health: `http://localhost:8088/healthz`
- Schema Registry: `http://localhost:8081`
- Kafka Connect: `http://localhost:8083`
- Neo4j Browser: `http://localhost:7474`
- MinIO console: `http://localhost:9001`
- OpenSearch: `http://localhost:9200`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Credentials in Compose are development-only examples.

## CDC limitation

The local profile uses Neo4j Community and therefore does not activate the CDC source connector. Use a licensed Neo4j Enterprise/AuraDB Enterprise environment and `connectors/neo4j-source/selected-cdc.json` to exercise CDC. The sink connector works with Community.

## Reset

```bash
./scripts/reset.sh
```

## Troubleshooting

- Kafka not healthy: inspect `docker compose logs kafka` and verify ports 29092/9093 are free.
- Connect plugin missing: rebuild `kafka-connect` without cache and confirm the 5.5.0 JAR exists under `/usr/share/java/neo4j`.
- No alert: inspect consumer logs in order: document-fetcher, stream-normalizer, nlp-worker, velato-worker.
- No graph node: inspect the connector status at `/connectors/signalchord-neo4j-sink/status` and the graph DLQ topic.
- Low-memory host: stop OpenSearch/Grafana first or raise Docker memory allocation.
