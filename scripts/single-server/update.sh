#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
DIGESTS=
RUNTIME_ENV=
TLS_SECRET=signalchord-ingress-tls

usage() {
  echo "usage: $0 --host HOST --digests IMAGE_DIGESTS --runtime-env FILE [--namespace NAME] [--tls-secret NAME]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --digests) DIGESTS=$2; shift 2 ;;
    --runtime-env) RUNTIME_ENV=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --tls-secret) TLS_SECRET=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$HOST" ] || [ -z "$DIGESTS" ] || [ -z "$RUNTIME_ENV" ]; then
  usage
  exit 2
fi

state_dir=${XDG_STATE_HOME:-$HOME/.local/state}/signalchord
mkdir -p "$state_dir"
chmod 700 "$state_dir"
if helm -n "$NAMESPACE" status signalchord >/dev/null 2>&1; then
  history_file=$(mktemp) || exit 1
  trap 'rm -f "$history_file"' EXIT INT TERM
  helm -n "$NAMESPACE" history signalchord -o json >"$history_file"
  revision=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[-1]["revision"])' "$history_file") || exit 1
  helm -n "$NAMESPACE" get values signalchord -a >"$state_dir/pre-update-revision-$revision.yaml"
  echo "saved current release values for Helm revision $revision"
fi

sh scripts/single-server/install.sh \
  --namespace "$NAMESPACE" \
  --host "$HOST" \
  --digests "$DIGESTS" \
  --runtime-env "$RUNTIME_ENV" \
  --tls-secret "$TLS_SECRET" \
  --yes
