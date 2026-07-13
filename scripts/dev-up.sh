#!/usr/bin/env sh
set -eu
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml:docker-compose.override.yml:docker-compose.projector.yml}
export COMPOSE_FILE

# Bring up stateful infrastructure first. Application consumers must not start
# until Kafka topics, the graph schema and local search settings exist.
docker compose --profile slice up -d --build --wait --wait-timeout 300 \
  kafka schema-registry neo4j postgres redis minio opensearch \
  otel-collector prometheus grafana sample-source

./scripts/create-topics.sh
./scripts/apply-graph-schema.sh
sh ./scripts/configure-opensearch.sh

# Start application services only after their durable dependencies are ready.
docker compose --profile slice up -d --build --wait --wait-timeout 300 \
  control-plane outbox-publisher document-fetcher stream-normalizer \
  nlp-worker entity-resolution claim-intelligence search-projector graph-query \
  graph-analytics-api graph-analytics-worker velato-api velato-worker \
  graph-projector alert-projector notification-worker realtime-gateway web

docker compose --profile slice run --rm feed-collector
printf '%s\n' "SignalChord v1: web http://localhost:5173 · API http://localhost:3000 · Graph query http://localhost:8090 · Analytics http://localhost:8092 · Neo4j http://localhost:7474 · Grafana http://localhost:3001"
