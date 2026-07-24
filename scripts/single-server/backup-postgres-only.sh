#!/usr/bin/env sh
set -eu

umask 077
NAMESPACE=signalchord
RUNTIME_ENV=
AGE_RECIPIENT=
CONFIRM=false
MINIO_ENDPOINT=
MINIO_SECURE=true
MINIO_BUCKET=
MINIO_ALIAS=signalchord-backup-dest
MINIO_ACCESS_KEY_FILE=
MINIO_SECRET_KEY_FILE=
STAGING=

usage() {
  echo "usage: $0 --runtime-env FILE --age-recipient RECIPIENT --minio-endpoint HOST:PORT --minio-bucket NAME \\
       --minio-access-key-file FILE --minio-secret-key-file FILE [--minio-insecure] [--namespace NAME] --yes" >&2
}

cleanup() {
  status=$?
  if [ -n "$STAGING" ]; then rm -rf "$STAGING"; fi
  exit "$status"
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --runtime-env) RUNTIME_ENV=$2; shift 2 ;;
    --age-recipient) AGE_RECIPIENT=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --minio-endpoint) MINIO_ENDPOINT=$2; shift 2 ;;
    --minio-bucket) MINIO_BUCKET=$2; shift 2 ;;
    --minio-alias) MINIO_ALIAS=$2; shift 2 ;;
    --minio-access-key-file) MINIO_ACCESS_KEY_FILE=$2; shift 2 ;;
    --minio-secret-key-file) MINIO_SECRET_KEY_FILE=$2; shift 2 ;;
    --minio-insecure) MINIO_SECURE=false; shift ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$RUNTIME_ENV" ] || [ -z "$AGE_RECIPIENT" ] || [ -z "$MINIO_ENDPOINT" ] || [ -z "$MINIO_BUCKET" ] \
  || [ -z "$MINIO_ACCESS_KEY_FILE" ] || [ -z "$MINIO_SECRET_KEY_FILE" ] || [ "$CONFIRM" != true ]; then
  usage
  exit 2
fi
[ -f "$RUNTIME_ENV" ] || { echo "runtime env file not found: $RUNTIME_ENV" >&2; exit 1; }
[ -f "$MINIO_ACCESS_KEY_FILE" ] || { echo "minio access key file not found: $MINIO_ACCESS_KEY_FILE" >&2; exit 1; }
[ -f "$MINIO_SECRET_KEY_FILE" ] || { echo "minio secret key file not found: $MINIO_SECRET_KEY_FILE" >&2; exit 1; }

for tool in kubectl mc age python3 sha256sum; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
runtime_mode=$(stat -c '%a' "$RUNTIME_ENV" 2>/dev/null || stat -f '%Lp' "$RUNTIME_ENV")
[ "$runtime_mode" = 600 ] || { echo "runtime env file must have mode 0600, got $runtime_mode" >&2; exit 1; }

kubectl get namespace "$NAMESPACE" >/dev/null

STAGING=$(mktemp -d "${TMPDIR:-/tmp}/signalchord-backup-postgres-only.XXXXXX")
mkdir -p "$STAGING/metadata" "$STAGING/data"
created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
created_at_path=$(date -u '+%Y-%m-%dT%H-%M-%SZ')
# kubectl config current-context has no meaning for an in-cluster CronJob
# ServiceAccount token (no kubeconfig is present), so this must not be fatal.
context=$(kubectl config current-context 2>/dev/null || echo in-cluster)

# This cadence is deliberately no-downtime: pg_dump takes an MVCC-consistent
# snapshot of a live, concurrently-written database. Nothing here scales any
# deployment or suspends the feed-collector cronjob.
# The variables below are expanded by the shell inside the PostgreSQL container.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec statefulset/postgres -- sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=9 --no-owner --no-acl' \
  > "$STAGING/data/postgres.dump"

age -r "$AGE_RECIPIENT" -o "$STAGING/runtime.env.age" "$RUNTIME_ENV"

python3 - "$STAGING/manifest.json" "$created_at" "$context" "$NAMESPACE" <<'PY'
import json, sys
path, created_at, context, namespace = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump({
        "format": "signalchord-single-server-backup-postgres-only",
        "version": 1,
        "created_at": created_at,
        "kubernetes_context": context,
        "namespace": namespace,
        "authoritative": ["postgresql", "runtime-config"],
        "application_quiesced": False,
    }, handle, indent=2)
    handle.write("\n")
PY
(
  cd "$STAGING"
  checksum_tmp=$(mktemp "${TMPDIR:-/tmp}/signalchord-checksums.XXXXXX")
  find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r file; do
    sha256sum "${file#./}"
  done > "$checksum_tmp"
  mv "$checksum_tmp" SHA256SUMS
)

minio_scheme=https
[ "$MINIO_SECURE" = true ] || minio_scheme=http
mc alias set "$MINIO_ALIAS" "$minio_scheme://$MINIO_ENDPOINT" \
  "$(cat "$MINIO_ACCESS_KEY_FILE")" "$(cat "$MINIO_SECRET_KEY_FILE")" >/dev/null
mc mb --ignore-existing "$MINIO_ALIAS/$MINIO_BUCKET" >/dev/null
mc mirror --quiet "$STAGING" "$MINIO_ALIAS/$MINIO_BUCKET/$created_at_path" >/dev/null

echo "SignalChord postgres-only backup completed: $MINIO_ALIAS/$MINIO_BUCKET/$created_at_path"
echo "Application deployments were not scaled or suspended for this backup."
