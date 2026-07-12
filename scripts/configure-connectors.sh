#!/usr/bin/env sh
set -eu
CONNECT_URL=${CONNECT_URL:-http://localhost:8083}
until curl -fsS "$CONNECT_URL/connectors" >/dev/null; do sleep 2; done
python3 -c 'import json,sys; json.dump(json.load(open("connectors/neo4j-sink/graph-mutations.json"))["config"], sys.stdout)' \
  | curl -fsS -X PUT -H 'Content-Type: application/json' --data-binary @- "$CONNECT_URL/connectors/signalchord-neo4j-sink/config" >/dev/null
printf '%s\n' "Neo4j sink connector configured. CDC source is intentionally disabled in the Community local profile."
