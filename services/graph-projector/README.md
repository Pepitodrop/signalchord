# Graph projector

First-party Kafka-to-Neo4j projector for the verified SignalChord runtime path. It consumes `graph.mutation-requested.v1`, applies allowlisted parameterized and idempotent Cypher mutations, and emits `graph.mutation-completed.v1`.

Malformed mutations are sent to `graph.mutation-requested.v1.dlq`. Transient Neo4j failures are not acknowledged, allowing the container or Kubernetes workload to restart and retry.

Kafka Connect remains an optional integration for environments that explicitly validate and operate the Neo4j connector. The local and CI reference path does not depend on a third-party connector plugin.
