#!/usr/bin/env sh
set -eu

# Thin safety wrapper around Kafka's own kafka-consumer-groups.sh --reset-offsets.
# This is deliberately NOT a custom replay engine: every offset-changing action
# below is a single kafka-consumer-groups.sh invocation, unmodified.
#
# Replay is only possible within a topic's retention window (30 days for
# standard topics, confirmed in
# infrastructure/kubernetes/helm/signalchord-community/templates/init-jobs.yaml;
# source.registered.v1 is compacted/infinite). Beyond that window replay is
# impossible -- a hard boundary of the architecture, not a limitation of this
# tool, and not something any flag here can override.

NAMESPACE=
GROUP=
TOPIC=
TO_DATETIME=
BOOTSTRAP_SERVER=kafka:9092
FORCE=false
CONFIRM=false
EVIDENCE_REPORT=

# The 9 known SignalChord consumer groups, traced directly from each Python
# worker's confluent_kafka.Consumer "group.id" (see services/*/worker.py).
# This list intentionally does NOT include the Go realtime-gateway consumer
# group (signalchord-realtime-gateway-v1); pass --force for any group outside
# this list, including a throwaway test/drill group.
KNOWN_GROUPS='
signalchord-alert-projector-v1
signalchord-entity-resolution-v1
signalchord-nlp-v1
signalchord-graph-analytics-v1
signalchord-graph-projector-v1
signalchord-velato-v1
signalchord-notification-worker-v1
signalchord-claim-intelligence-v1
signalchord-search-projector-v1
'

usage() {
  echo "usage: $0 --namespace NAME --group GROUP --topic TOPIC --to-datetime TIMESTAMP --yes \\
       [--force] [--bootstrap-server HOST:PORT] [--evidence-report FILE]" >&2
  echo >&2
  echo "There is no default --namespace or --group: both must always be given explicitly." >&2
  echo "Replay only works within a topic's retention window (30 days for standard topics)." >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --namespace) NAMESPACE=$2; shift 2 ;;
    --group) GROUP=$2; shift 2 ;;
    --topic) TOPIC=$2; shift 2 ;;
    --to-datetime) TO_DATETIME=$2; shift 2 ;;
    --bootstrap-server) BOOTSTRAP_SERVER=$2; shift 2 ;;
    --evidence-report) EVIDENCE_REPORT=$2; shift 2 ;;
    --force) FORCE=true; shift ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$NAMESPACE" ] || [ -z "$GROUP" ] || [ -z "$TOPIC" ] || [ -z "$TO_DATETIME" ] || [ "$CONFIRM" != true ]; then
  usage
  exit 2
fi

for tool in kubectl python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

if [ -n "$EVIDENCE_REPORT" ]; then
  evidence_dir=$(dirname "$EVIDENCE_REPORT")
  [ -d "$evidence_dir" ] || { echo "evidence report directory not found: $evidence_dir" >&2; exit 1; }
fi

if [ "$FORCE" != true ]; then
  known=false
  for candidate in $KNOWN_GROUPS; do
    if [ "$candidate" = "$GROUP" ]; then
      known=true
      break
    fi
  done
  if [ "$known" != true ]; then
    echo "refusing to replay: '$GROUP' is not one of the known SignalChord consumer groups" >&2
    echo "known groups:$(printf '%s' "$KNOWN_GROUPS" | tr '\n' ' ')" >&2
    echo "pass --force to proceed anyway (e.g. against a throwaway test/drill group)" >&2
    exit 1
  fi
fi

kubectl get namespace "$NAMESPACE" >/dev/null

echo "== Current offsets: namespace=$NAMESPACE group=$GROUP =="
before_offsets=$(kubectl -n "$NAMESPACE" exec statefulset/kafka -- \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "$BOOTSTRAP_SERVER" \
  --describe --group "$GROUP")
echo "$before_offsets"

echo
echo "== Proposed reset (dry run): group=$GROUP topic=$TOPIC to-datetime=$TO_DATETIME =="
kubectl -n "$NAMESPACE" exec statefulset/kafka -- \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "$BOOTSTRAP_SERVER" \
  --group "$GROUP" --topic "$TOPIC" --reset-offsets --to-datetime "$TO_DATETIME" --dry-run

echo
echo "Note: if --to-datetime falls outside this topic's retention window, Kafka resets to" \
     "the earliest still-retained offset instead of the requested time -- replay beyond" \
     "retention is not possible, by design, and this tool cannot work around that."
echo
echo "Executing the reset shown above (confirmed via --yes): namespace=$NAMESPACE group=$GROUP topic=$TOPIC"

created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

kubectl -n "$NAMESPACE" exec statefulset/kafka -- \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "$BOOTSTRAP_SERVER" \
  --group "$GROUP" --topic "$TOPIC" --reset-offsets --to-datetime "$TO_DATETIME" --execute

echo
echo "== Offsets after reset: namespace=$NAMESPACE group=$GROUP =="
after_offsets=$(kubectl -n "$NAMESPACE" exec statefulset/kafka -- \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "$BOOTSTRAP_SERVER" \
  --describe --group "$GROUP")
echo "$after_offsets"

if [ -n "$EVIDENCE_REPORT" ]; then
  REPLAY_CREATED_AT="$created_at" REPLAY_NAMESPACE="$NAMESPACE" REPLAY_GROUP="$GROUP" \
  REPLAY_TOPIC="$TOPIC" REPLAY_TO_DATETIME="$TO_DATETIME" REPLAY_BOOTSTRAP_SERVER="$BOOTSTRAP_SERVER" \
  REPLAY_BEFORE_OFFSETS="$before_offsets" REPLAY_AFTER_OFFSETS="$after_offsets" \
  python3 - "$EVIDENCE_REPORT" <<'PY'
# Appends one JSON-Lines record per invocation. Append-only by construction:
# opened in "a" mode, so pre-existing evidence in the report file (in any
# format) is never read, rewritten or truncated.
import json
import os
import sys

path = sys.argv[1]
record = {
    "tool": "replay-kafka.sh",
    "created_at": os.environ["REPLAY_CREATED_AT"],
    "namespace": os.environ["REPLAY_NAMESPACE"],
    "group": os.environ["REPLAY_GROUP"],
    "topic": os.environ["REPLAY_TOPIC"],
    "to_datetime": os.environ["REPLAY_TO_DATETIME"],
    "bootstrap_server": os.environ["REPLAY_BOOTSTRAP_SERVER"],
    "offsets_before": os.environ["REPLAY_BEFORE_OFFSETS"],
    "offsets_after": os.environ["REPLAY_AFTER_OFFSETS"],
}
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True))
    handle.write("\n")
PY
  echo
  echo "Replay evidence appended to $EVIDENCE_REPORT"
fi
