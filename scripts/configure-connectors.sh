#!/usr/bin/env sh
set -eu
CONNECT_URL=${CONNECT_URL:-http://localhost:8083}
until curl -fsS "$CONNECT_URL/connectors" >/dev/null; do sleep 2; done
curl -fsS -X PUT -H 'Content-Type: application/json' --data @connectors/neo4j-sink/graph-mutations.json "$CONNECT_URL/connectors/signalchord-neo4j-sink/config" >/dev/null
printf '%s\n' "Neo4j sink connector configured. CDC source is intentionally disabled in the Community local profile."
