#!/usr/bin/env sh
set -eu
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml:docker-compose.override.yml:docker-compose.projector.yml}
export COMPOSE_FILE
TOKEN=${SIGNALCHORD_TOKEN:-signalchord-dev-token}
API=${SIGNALCHORD_API_URL:-http://localhost:${CONTROL_PLANE_HOST_PORT:-3000}}
OPENSEARCH_URL=${OPENSEARCH_URL:-http://localhost:${OPENSEARCH_HOST_PORT:-9200}}
REALTIME_URL=${REALTIME_URL:-http://localhost:${REALTIME_HOST_PORT:-8088}}
GRAPH_QUERY_URL=${GRAPH_QUERY_URL:-http://localhost:${GRAPH_QUERY_HOST_PORT:-8090}}
VELATO_URL=${VELATO_URL:-http://localhost:${VELATO_HOST_PORT:-8091}}
GRAPH_ANALYTICS_URL=${GRAPH_ANALYTICS_URL:-http://localhost:${GRAPH_ANALYTICS_HOST_PORT:-8092}}
WEB_URL=${WEB_URL:-http://localhost:${WEB_HOST_PORT:-5173}}

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/smoke-test-lib.sh
. "$SCRIPT_DIR/smoke-test-lib.sh"

check_url() {
  curl -fsS "$1" >/dev/null
}

check_api_health() {
  curl -fsS "$API/healthz" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'
}

check_api_contains() {
  endpoint=$1
  expected=$2
  curl -fsS -H "Authorization: Bearer $TOKEN" "$API$endpoint" | grep -Fq "$expected"
}

check_alert() {
  check_api_contains "/api/v1/alerts" "alert_score"
}

neo4j_count_at_least() {
  query=$1
  minimum=$2
  count=$(docker compose exec -T neo4j cypher-shell -u neo4j -p signalchord-dev --format plain "$query" | tail -n 1 | tr -d '"\r')
  case ${count:-} in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ "$count" -ge "$minimum" ]
}

check_search_projection() {
  curl -fsS -H 'Content-Type: application/json' "$OPENSEARCH_URL/signalchord-entities/_search" \
    -d '{"query":{"match_all":{}}}' | grep -Fq 'company:acme'
}

check_graph_analytics() {
  curl -fsS -H 'Content-Type: application/json' "$GRAPH_ANALYTICS_URL/v1/analyze" \
    -d '{"tenant_id":"00000000-0000-4000-8000-000000000001","entity_id":"company:acme","lookback_days":30}' \
    | grep -Fq 'graph_centrality'
}

wait_for "OpenSearch readiness" check_url "$OPENSEARCH_URL/_cluster/health"
wait_for "realtime gateway readiness" check_url "$REALTIME_URL/healthz"
wait_for "graph query readiness" check_url "$GRAPH_QUERY_URL/healthz"
wait_for "Velato readiness" check_url "$VELATO_URL/healthz"
wait_for "graph analytics readiness" check_url "$GRAPH_ANALYTICS_URL/healthz"
wait_for "control-plane readiness" check_api_health
wait_for "fixture source seeding" check_api_contains "/api/v1/sources" "Fixture Feed"
wait_for "fixture watchlist seeding" check_api_contains "/api/v1/watchlists" "company:acme"

docker compose --profile slice run --rm feed-collector >/dev/null

wait_for "durable alert creation" check_alert
wait_for "Document graph projection" neo4j_count_at_least "MATCH (d:Document) RETURN count(d)" 1
wait_for "Entity graph projection" neo4j_count_at_least "MATCH (e:Entity) RETURN count(e)" 2
wait_for "Claim graph projection" neo4j_count_at_least "MATCH (c:Claim) RETURN count(c)" 1
wait_for "partnership relationship projection" neo4j_count_at_least "MATCH ()-[r:PARTNERED_WITH]->() RETURN count(r)" 1
wait_for "OpenSearch entity projection" check_search_projection
wait_for "graph analytics result" check_graph_analytics
wait_for "web application readiness" check_url "$WEB_URL/"

echo "SignalChord v1 article-to-alert smoke test passed."
