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

[ -n "$HOST" ] && [ -n "$DIGESTS" ] && [ -n "$RUNTIME_ENV" ] || { usage; exit 2; }

state_dir=${XDG_STATE_HOME:-$HOME/.local/state}/signalchord
mkdir -p "$state_dir"
chmod 700 "$state_dir"
if helm -n "$NAMESPACE" status signalchord >/dev/null 2>&1; then
  revision=$(helm -n "$NAMESPACE" history signalchord -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)[-1]["revision"])')
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
