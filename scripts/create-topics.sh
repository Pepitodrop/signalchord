#!/usr/bin/env sh
set -eu
TOPICS="source.registered.v1 source.poll.requested.v1 source.document.discovered.v1 source.document.fetched.v1 source.takedown.requested.v1 document.normalized.v1 document.duplicate-detected.v1 document.nlp-requested.v1 document.nlp-completed.v1 entity.mention-extracted.v1 entity.resolution-requested.v1 entity.resolved.v1 claim.extracted.v1 claim.clustered.v1 claim.contradiction-detected.v1 relationship.extracted.v1 graph.mutation-requested.v1 graph.mutation-completed.v1 graph.analytics-requested.v1 intelligence.signal-created.v1 alert.policy-evaluation-requested.v1 alert.created.v1 notification.requested.v1 tenant.export.requested.v1 tenant.deletion.requested.v1 audit.event.v1"
for topic in $TOPICS; do
  cleanup="delete"
  retention="2592000000"
  if [ "$topic" = "source.registered.v1" ]; then cleanup="compact"; retention="-1"; fi
  docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic "$topic" --partitions 6 --replication-factor 1 --config cleanup.policy="$cleanup" --config retention.ms="$retention"
  docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic "$topic.dlq" --partitions 3 --replication-factor 1 --config cleanup.policy=delete --config retention.ms=2592000000
done
