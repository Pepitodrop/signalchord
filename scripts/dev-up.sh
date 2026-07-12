#!/usr/bin/env sh
set -eu

docker compose --profile slice up -d --build \
  kafka schema-registry neo4j postgres redis minio opensearch otel-collector prometheus grafana kafka-connect \
  sample-source control-plane outbox-publisher document-fetcher stream-normalizer nlp-worker entity-resolution \
  claim-intelligence search-projector graph-query velato-api velato-worker alert-projector realtime-gateway web

./scripts/create-topics.sh
./scripts/apply-graph-schema.sh
./scripts/configure-connectors.sh

docker compose --profile slice run --rm feed-collector
printf '%s\n' "SignalChord v1: web http://localhost:5173 · API http://localhost:3000 · Neo4j http://localhost:7474 · Grafana http://localhost:3001"
