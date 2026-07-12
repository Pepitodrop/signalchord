# ADR 0007 — Use a first-party graph projector for the required runtime

**Status:** Accepted

## Context

The article-to-alert path requires deterministic, replayable and idempotent projection of allowlisted graph mutations into Neo4j. The original local path depended on a third-party Kafka Connect plugin downloaded during image construction. Connector configuration compatibility varies across plugin, converter, Kafka Connect and Neo4j versions, and a rejected connector configuration prevented the otherwise healthy reference stack from starting.

## Decision

The required local and initial production path uses a first-party Python `graph-projector` Kafka consumer. It validates a closed mutation vocabulary, constructs only static parameterized Cypher, writes nodes through a global `GraphNode(stable_id)` identity, emits completion events and routes permanently malformed mutations to a DLQ.

Kafka Connect templates remain available behind an optional profile for environments that independently validate and operate the connector stack.

## Consequences

- The reference runtime no longer depends on downloading or configuring a third-party connector plugin.
- Projection semantics, tests and release compatibility live in the SignalChord repository.
- The projector must be operated like any other at-least-once consumer: lag, failures, DLQ volume and Neo4j latency require monitoring.
- Optional CDC or Kafka Connect integrations still require edition/licensing review and a separate compatibility gate.
