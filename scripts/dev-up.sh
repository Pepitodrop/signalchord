#!/usr/bin/env sh
set -eu
docker compose up -d --build kafka schema-registry neo4j postgres redis minio opensearch otel-collector prometheus grafana kafka-connect
./scripts/create-topics.sh
./scripts/apply-graph-schema.sh
./scripts/configure-connectors.sh
docker compose --profile slice up -d --build sample-source document-fetcher stream-normalizer nlp-worker velato-worker realtime-gateway web
docker compose --profile slice run --rm feed-collector
printf '%s\n' "SignalChord: web http://localhost:5173 · Neo4j http://localhost:7474 · Grafana http://localhost:3001"
