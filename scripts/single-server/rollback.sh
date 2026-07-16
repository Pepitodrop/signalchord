#!/usr/bin/env sh
set -eu

NAMESPACE=signalchord
HOST=
REVISION=
INSECURE=false

usage() {
  echo "usage: $0 --revision NUMBER --host HOST [--namespace NAME] [--insecure]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --revision) REVISION=$2; shift 2 ;;
    --host) HOST=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --insecure) INSECURE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$REVISION" ] || [ -z "$HOST" ]; then
  usage
  exit 2
fi
case "$REVISION" in *[!0-9]*|'') echo "revision must be numeric" >&2; exit 2 ;; esac

helm -n "$NAMESPACE" history signalchord
helm -n "$NAMESPACE" rollback signalchord "$REVISION" --wait --timeout 20m

if [ "$INSECURE" = true ]; then
  sh scripts/single-server/health.sh --namespace "$NAMESPACE" --host "$HOST" --insecure
else
  sh scripts/single-server/health.sh --namespace "$NAMESPACE" --host "$HOST"
fi

echo "rolled SignalChord back to Helm revision $REVISION"
