#!/usr/bin/env sh
set -eu
for file in graph/migrations/*.cypher; do
  printf 'Applying %s\n' "$file"
  docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev < "$file"
done
