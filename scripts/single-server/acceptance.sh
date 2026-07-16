#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
TOKEN_FILE=
INSECURE=false
TIMEOUT=1200
ALLOW_EXISTING_ALERT=false
JOB=

usage() {
  echo "usage: $0 --host HOST --token-file FILE [--namespace NAME] [--timeout SECONDS] [--allow-existing-alert] [--insecure]" >&2
}
cleanup() {
  status=$?
  [ -z "$JOB" ] || kubectl -n "$NAMESPACE" delete job "$JOB" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --token-file) TOKEN_FILE=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --timeout) TIMEOUT=$2; shift 2 ;;
    --allow-existing-alert) ALLOW_EXISTING_ALERT=true; shift ;;
    --insecure) INSECURE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$HOST" ] && [ -n "$TOKEN_FILE" ] || { usage; exit 2; }
[ -s "$TOKEN_FILE" ] || { echo "token file not found or empty: $TOKEN_FILE" >&2; exit 1; }
for tool in kubectl helm curl python3; do command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }; done
TOKEN=$(sed -n '1p' "$TOKEN_FILE")
[ -n "$TOKEN" ] || { echo "token file is empty" >&2; exit 1; }
BASE_URL="https://$HOST"
CURL_TLS=
if [ "$INSECURE" = true ]; then CURL_TLS=--insecure; fi

health_args="--namespace $NAMESPACE --host $HOST"
if [ "$INSECURE" = true ]; then health_args="$health_args --insecure"; fi
# shellcheck disable=SC2086
sh scripts/single-server/health.sh $health_args
helm -n "$NAMESPACE" status signalchord >/dev/null
helm -n "$NAMESPACE" status signalchord-community >/dev/null

api_get() {
  path=$1
  # shellcheck disable=SC2086
  curl --fail --silent --show-error --max-time 30 $CURL_TLS \
    -H "Authorization: Bearer $TOKEN" -H 'Accept: application/json' "$BASE_URL$path"
}
json_count() {
  python3 -c 'import json,sys; value=json.load(sys.stdin); assert isinstance(value,list); print(len(value))'
}

sources_before=$(api_get /api/v1/sources | json_count)
watchlists=$(api_get /api/v1/watchlists | json_count)
alerts_before=$(api_get /api/v1/alerts | json_count)
[ "$sources_before" -gt 0 ] || { echo "acceptance requires at least one permitted source" >&2; exit 1; }
[ "$watchlists" -gt 0 ] || { echo "acceptance requires at least one watchlist" >&2; exit 1; }

JOB="signalchord-acceptance-$(date +%s)"
kubectl -n "$NAMESPACE" create job --from=cronjob/signalchord-feed-collector "$JOB" >/dev/null
if ! kubectl -n "$NAMESPACE" wait --for=condition=complete "job/$JOB" --timeout="${TIMEOUT}s" >/dev/null; then
  kubectl -n "$NAMESPACE" logs "job/$JOB" --all-containers=true >&2 || true
  exit 1
fi
kubectl -n "$NAMESPACE" logs "job/$JOB" --all-containers=true

started=$(date +%s)
while :; do
  alerts_after=$(api_get /api/v1/alerts | json_count)
  if [ "$alerts_after" -gt "$alerts_before" ]; then
    break
  fi
  if [ "$ALLOW_EXISTING_ALERT" = true ] && [ "$alerts_after" -gt 0 ]; then
    break
  fi
  now=$(date +%s)
  if [ $((now - started)) -ge "$TIMEOUT" ]; then
    echo "article-to-alert acceptance timed out: alerts before=$alerts_before after=$alerts_after" >&2
    exit 1
  fi
  sleep 10
done

api_get /api/v1/alerts | python3 -c 'import json,sys; rows=json.load(sys.stdin); assert rows and all("alert_score" in row for row in rows)'
kubectl -n "$NAMESPACE" get pvc -o json | python3 -c 'import json,sys; data=json.load(sys.stdin); bad=[x["metadata"]["name"] for x in data["items"] if x.get("status",{}).get("phase")!="Bound"]; assert not bad, bad'
echo "SignalChord Kubernetes acceptance passed: sources=$sources_before watchlists=$watchlists alerts=$alerts_after"
