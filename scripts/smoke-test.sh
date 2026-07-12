#!/usr/bin/env sh
set -eu
curl -fsS http://localhost:8081/subjects >/dev/null
curl -fsS http://localhost:8083/connectors >/dev/null
curl -fsS http://localhost:9200/_cluster/health >/dev/null
curl -fsS http://localhost:8088/healthz >/dev/null
curl -fsS http://localhost:5173/ >/dev/null

docker compose --profile slice run --rm feed-collector >/dev/null
found=0
attempt=0
while [ "$attempt" -lt 24 ]; do
  if docker compose exec -T kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic alert.created.v1 --from-beginning --max-messages 1 --timeout-ms 5000 2>/dev/null | grep -q 'alert.created.v1'; then
    found=1
    break
  fi
  attempt=$((attempt + 1))
done
[ "$found" -eq 1 ] || { echo "No alert event observed" >&2; exit 1; }
count=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "MATCH (d:Document) RETURN count(d) AS count" | tail -n 1 | tr -d '"\r')
[ "${count:-0}" -ge 1 ] || { echo "No Document node observed" >&2; exit 1; }
echo "SignalChord article-to-alert smoke test passed."
