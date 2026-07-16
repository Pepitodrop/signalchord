#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
DIGESTS=
RUNTIME_ENV=
TLS_SECRET=signalchord-ingress-tls
CONFIRM=false

usage() {
  echo "usage: $0 --host HOST --digests IMAGE_DIGESTS --runtime-env FILE [--namespace NAME] [--tls-secret NAME] --yes" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --digests) DIGESTS=$2; shift 2 ;;
    --runtime-env) RUNTIME_ENV=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --tls-secret) TLS_SECRET=$2; shift 2 ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$HOST" ] && [ -n "$DIGESTS" ] && [ -n "$RUNTIME_ENV" ] && [ "$CONFIRM" = true ] || { usage; exit 2; }
[ -f "$DIGESTS" ] || { echo "digest file not found: $DIGESTS" >&2; exit 1; }
[ -f "$RUNTIME_ENV" ] || { echo "runtime env file not found: $RUNTIME_ENV" >&2; exit 1; }

for tool in kubectl helm python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

context=$(kubectl config current-context)
echo "Deploying SignalChord to Kubernetes context: $context"
echo "Namespace: $NAMESPACE"
echo "Host: $HOST"

if [ -r /proc/sys/vm/max_map_count ]; then
  vm_max_map_count=$(cat /proc/sys/vm/max_map_count)
  if [ "$vm_max_map_count" -lt 262144 ]; then
    echo "vm.max_map_count must be at least 262144 for OpenSearch" >&2
    echo "Run: sudo sysctl -w vm.max_map_count=262144 and persist it in /etc/sysctl.d" >&2
    exit 1
  fi
fi

runtime_mode=$(stat -c '%a' "$RUNTIME_ENV" 2>/dev/null || stat -f '%Lp' "$RUNTIME_ENV")
[ "$runtime_mode" = 600 ] || { echo "runtime env file must have mode 0600, got $runtime_mode" >&2; exit 1; }

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT INT TERM
python3 scripts/single-server/render_digest_values.py "$DIGESTS" "$workdir/image-digests.yaml"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl label namespace "$NAMESPACE" pod-security.kubernetes.io/enforce=restricted --overwrite >/dev/null
kubectl -n "$NAMESPACE" create secret generic signalchord-runtime \
  --from-env-file="$RUNTIME_ENV" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

if ! kubectl -n "$NAMESPACE" get secret "$TLS_SECRET" >/dev/null 2>&1; then
  echo "TLS secret $TLS_SECRET is missing in namespace $NAMESPACE" >&2
  echo "Create it before installation: kubectl -n $NAMESPACE create secret tls $TLS_SECRET --cert CERT.pem --key KEY.pem" >&2
  exit 1
fi

helm upgrade --install signalchord-community \
  infrastructure/kubernetes/helm/signalchord-community \
  --namespace "$NAMESPACE" \
  --wait --timeout 20m

helm upgrade --install signalchord \
  infrastructure/kubernetes/helm/signalchord \
  --namespace "$NAMESPACE" \
  --values infrastructure/kubernetes/helm/signalchord/values-single-server.yaml \
  --values "$workdir/image-digests.yaml" \
  --set-string ingress.host="$HOST" \
  --set-string ingress.tlsSecretName="$TLS_SECRET" \
  --set-string global.config.webOrigin="https://$HOST" \
  --wait --timeout 20m

scripts/single-server/health.sh --namespace "$NAMESPACE" --host "$HOST"
echo "SignalChord installation completed for https://$HOST"
