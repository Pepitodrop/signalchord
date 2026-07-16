#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
OUTPUT=
CONFIRM=false

usage() {
  echo "usage: $0 --output DIR [--namespace NAME] --yes" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) OUTPUT=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$OUTPUT" ] || [ "$CONFIRM" != true ]; then
  usage
  exit 2
fi
for tool in kubectl helm gzip sha256sum; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

umask 077
mkdir -p "$OUTPUT"
[ -z "$(find "$OUTPUT" -mindepth 1 -maxdepth 1 -print -quit)" ] || {
  echo "output directory must be empty: $OUTPUT" >&2
  exit 1
}

date -u +%Y-%m-%dT%H:%M:%SZ >"$OUTPUT/created-at.txt"
kubectl config current-context >"$OUTPUT/kubernetes-context.txt"
kubectl version -o yaml >"$OUTPUT/kubernetes-version.yaml"
helm version --template '{{ .Version }}' >"$OUTPUT/helm-version.txt"
helm -n "$NAMESPACE" get values signalchord -a >"$OUTPUT/signalchord-values.yaml"
helm -n "$NAMESPACE" get values signalchord-community -a >"$OUTPUT/community-values.yaml"
helm -n "$NAMESPACE" history signalchord -o json >"$OUTPUT/signalchord-history.json"
kubectl -n "$NAMESPACE" get all,pvc,ingress,networkpolicy -o yaml >"$OUTPUT/kubernetes-resources.yaml"

postgres_pod=$(kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=postgres -o jsonpath='{.items[0].metadata.name}') || exit 1
[ -n "$postgres_pod" ] || { echo "PostgreSQL pod not found" >&2; exit 1; }
# Variables expand inside the remote pod shell, not locally.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec "$postgres_pod" -- sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip -9 >"$OUTPUT/postgres.sql.gz"

kubectl -n "$NAMESPACE" get pvc \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,VOLUME:.spec.volumeName,STORAGE:.spec.resources.requests.storage,CLASS:.spec.storageClassName' \
  --no-headers >"$OUTPUT/pvc-inventory.tsv"
[ -s "$OUTPUT/pvc-inventory.tsv" ] || { echo "no persistent volume claims found" >&2; exit 1; }

cat >"$OUTPUT/README.txt" <<'EOF'
This bundle contains a PostgreSQL logical dump, Helm values/history, Kubernetes metadata and a
complete namespace PVC inventory. It intentionally does not export Kubernetes Secrets. Back up
runtime credentials separately in an encrypted password manager or offline encrypted archive.
Stateful PVC data must be copied while each owning workload is stopped, using the documented
offline snapshot procedure.
EOF

(
  cd "$OUTPUT"
  sha256sum ./* >SHA256SUMS
)
echo "backup metadata and PostgreSQL dump written to $OUTPUT"
