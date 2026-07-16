#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
INSECURE=false

usage() {
  echo "usage: $0 --host HOST [--namespace NAME] [--insecure]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --insecure) INSECURE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$HOST" ] || { usage; exit 2; }
for tool in kubectl curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

for resource in \
  statefulset/kafka statefulset/postgres statefulset/neo4j statefulset/valkey \
  statefulset/minio statefulset/opensearch; do
  kubectl -n "$NAMESPACE" rollout status "$resource" --timeout=10m
done

kubectl -n "$NAMESPACE" get deployment -l app.kubernetes.io/part-of=signalchord -o name |
  while IFS= read -r deployment; do
    [ -n "$deployment" ] || continue
    kubectl -n "$NAMESPACE" rollout status "$deployment" --timeout=10m
  done

not_ready=$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/part-of=signalchord \
  -o jsonpath='{range .items[?(@.status.phase!="Running")]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}')
if [ -n "$not_ready" ]; then
  echo "SignalChord pods are not running:" >&2
  echo "$not_ready" >&2
  exit 1
fi

pending_pvcs=$(kubectl -n "$NAMESPACE" get pvc -o jsonpath='{range .items[?(@.status.phase!="Bound")]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}')
if [ -n "$pending_pvcs" ]; then
  echo "SignalChord persistent volume claims are not bound:" >&2
  echo "$pending_pvcs" >&2
  exit 1
fi

if [ "$INSECURE" = true ]; then
  curl --fail --silent --show-error --max-time 15 --insecure "https://$HOST/healthz" >/dev/null
else
  curl --fail --silent --show-error --max-time 15 "https://$HOST/healthz" >/dev/null
fi

echo "SignalChord workloads, storage and ingress are healthy"
