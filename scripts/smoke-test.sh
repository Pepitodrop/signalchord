#!/usr/bin/env sh
set -eu
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml:docker-compose.override.yml:docker-compose.projector.yml}
export COMPOSE_FILE
TOKEN=${SIGNALCHORD_TOKEN:-signalchord-dev-token}
API=${SIGNALCHORD_API_URL:-http://localhost:3000}

curl -fsS http://localhost:8081/subjects >/dev/null
curl -fsS http://localhost:9200/_cluster/health >/dev/null
curl -fsS http://localhost:8088/healthz >/dev/null
curl -fsS http://localhost:8090/healthz >/dev/null
curl -fsS http://localhost:8091/healthz >/dev/null
curl -fsS http://localhost:8092/healthz >/dev/null
curl -fsS "$API/healthz" | grep -q '"status":"ok"'
curl -fsS -H "Authorization: Bearer $TOKEN" "$API/api/v1/sources" | grep -q 'Fixture Feed'
curl -fsS -H "Authorization: Bearer $TOKEN" "$API/api/v1/watchlists" | grep -q 'company:acme'

docker compose --profile slice run --rm feed-collector >/dev/null

attempt=0
while [ "$attempt" -lt 36 ]; do
  if curl -fsS -H "Authorization: Bearer $TOKEN" "$API/api/v1/alerts" | grep -q 'alert_score'; then break; fi
  attempt=$((attempt + 1)); sleep 5
done
[ "$attempt" -lt 36 ] || { echo "No durable alert observed" >&2; exit 1; }

count=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "MATCH (d:Document) RETURN count(d)" | tail -n 1 | tr -d '"\r')
[ "${count:-0}" -ge 1 ] || { echo "No Document node observed" >&2; exit 1; }
entities=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "MATCH (e:Entity) RETURN count(e)" | tail -n 1 | tr -d '"\r')
[ "${entities:-0}" -ge 2 ] || { echo "Expected resolved entities" >&2; exit 1; }
claims=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "MATCH (c:Claim) RETURN count(c)" | tail -n 1 | tr -d '"\r')
[ "${claims:-0}" -ge 1 ] || { echo "Expected extracted claims" >&2; exit 1; }
relations=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "MATCH ()-[r:PARTNERED_WITH]->() RETURN count(r)" | tail -n 1 | tr -d '"\r')
[ "${relations:-0}" -ge 1 ] || { echo "Expected partnership relationship" >&2; exit 1; }

curl -fsS -H 'Content-Type: application/json' http://localhost:9200/signalchord-entities/_search -d '{"query":{"match_all":{}}}' | grep -q 'company:acme'
curl -fsS -H 'Content-Type: application/json' http://localhost:8092/v1/analyze \
  -d '{"tenant_id":"00000000-0000-4000-8000-000000000001","entity_id":"company:acme","lookback_days":30}' \
  | grep -q 'graph_centrality'
curl -fsS http://localhost:5173/ >/dev/null

echo "SignalChord v1 article-to-alert smoke test passed."
