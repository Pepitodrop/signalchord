#!/usr/bin/env sh
set -eu

# Writes one deterministic "table|count|checksum" line per table to --output,
# for comparing a namespace's seeded/backed-up Postgres state against a
# restored namespace's Postgres state (see docs/specs/
# recovery-and-replay-hardening.md §24.9 steps 3/7). The checksum is an md5
# of the table's ids concatenated in a fixed order, so an exact reordering-
# independent comparison is possible via a plain `diff` of two runs' output.
#
# The SQL itself is built entirely in this outer shell and piped over stdin
# to a fixed, non-interpolated `psql` invocation inside the pod -- avoiding
# any nested quoting between this script, kubectl exec, an inner sh -c, and
# psql's own -c argument.

NAMESPACE=
OUTPUT=
TABLES="organizations users memberships api_tokens sources watchlists watchlist_items policies policy_versions"

usage() {
  echo "usage: $0 --namespace NAME --output FILE [--tables \"t1 t2 ...\"]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --namespace) NAMESPACE=$2; shift 2 ;;
    --output) OUTPUT=$2; shift 2 ;;
    --tables) TABLES=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$NAMESPACE" ] || [ -z "$OUTPUT" ]; then
  usage
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"
: > "$OUTPUT"

for table in $TABLES; do
  sql="SELECT count(*), COALESCE(md5(string_agg(id::text, ',' ORDER BY id)), '') FROM \"${table}\";"
  # shellcheck disable=SC2016
  row=$(printf '%s\n' "$sql" | kubectl -n "$NAMESPACE" exec -i statefulset/postgres -- \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -F "|"')
  count=$(printf '%s' "$row" | cut -d'|' -f1)
  checksum=$(printf '%s' "$row" | cut -d'|' -f2)
  echo "${table}|${count}|${checksum}" >> "$OUTPUT"
done
