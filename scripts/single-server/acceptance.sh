#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
CANARY_COMMAND=
INSECURE=false

usage() {
  echo "usage: $0 --host HOST [--namespace NAME] [--canary-command COMMAND] [--insecure]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --canary-command) CANARY_COMMAND=$2; shift 2 ;;
    --insecure) INSECURE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$HOST" ] || { usage; exit 2; }
for tool in kubectl helm curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

if [ "$INSECURE" = true ]; then
  sh scripts/single-server/health.sh --namespace "$NAMESPACE" --host "$HOST" --insecure
else
  sh scripts/single-server/health.sh --namespace "$NAMESPACE" --host "$HOST"
fi

helm -n "$NAMESPACE" status signalchord >/dev/null
helm -n "$NAMESPACE" status signalchord-community >/dev/null

mutable=$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/part-of=signalchord -o jsonpath='{range .items[*].spec.containers[*]}{.image}{"\n"}{end}' | grep -Ev '@sha256:[0-9a-f]{64}$' || true)
[ -z "$mutable" ] || { echo "non-digest application images detected:" >&2; echo "$mutable" >&2; exit 1; }

external_services=$(kubectl -n "$NAMESPACE" get services -l app.kubernetes.io/part-of=signalchord -o jsonpath='{range .items[?(@.spec.type!="ClusterIP")]}{.metadata.name}{" "}{.spec.type}{"\n"}{end}')
[ -z "$external_services" ] || { echo "unexpected externally exposed services:" >&2; echo "$external_services" >&2; exit 1; }

kubectl -n "$NAMESPACE" get networkpolicy signalchord-default-deny >/dev/null
kubectl -n "$NAMESPACE" get ingress signalchord >/dev/null

if [ "$INSECURE" = true ]; then
  curl --fail --silent --show-error --max-time 20 --insecure "https://$HOST/" >/dev/null
  curl --fail --silent --show-error --max-time 20 --insecure "https://$HOST/healthz" >/dev/null
else
  curl --fail --silent --show-error --max-time 20 "https://$HOST/" >/dev/null
  curl --fail --silent --show-error --max-time 20 "https://$HOST/healthz" >/dev/null
fi

if [ -n "$CANARY_COMMAND" ]; then
  sh -c "$CANARY_COMMAND"
else
  echo "No article-to-alert canary command supplied; infrastructure acceptance only."
fi

echo "SignalChord Kubernetes acceptance checks passed"
