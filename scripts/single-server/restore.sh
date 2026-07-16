#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
BACKUP=
CONFIRM=

usage() {
  echo "usage: $0 --backup DIR [--namespace NAME] --confirm RESTORE-SIGNALCHORD" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup) BACKUP=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --confirm) CONFIRM=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$BACKUP" ] || [ "$CONFIRM" != RESTORE-SIGNALCHORD ]; then
  usage
  exit 2
fi
for tool in kubectl gzip sha256sum; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
[ -f "$BACKUP/SHA256SUMS" ] || { echo "missing SHA256SUMS" >&2; exit 1; }
[ -f "$BACKUP/postgres.sql.gz" ] || { echo "missing PostgreSQL dump" >&2; exit 1; }
(cd "$BACKUP" && sha256sum -c SHA256SUMS)

postgres_pod=$(kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=postgres -o jsonpath='{.items[0].metadata.name}') || exit 1
[ -n "$postgres_pod" ] || { echo "PostgreSQL pod not found" >&2; exit 1; }

# shellcheck disable=SC2016 -- variables expand inside the remote pod shell, not locally.
gzip -dc "$BACKUP/postgres.sql.gz" | kubectl -n "$NAMESPACE" exec -i "$postgres_pod" -- sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'

echo "PostgreSQL restore completed. Restore offline PVC snapshots separately, then run acceptance.sh."
