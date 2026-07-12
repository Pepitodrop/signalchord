# ADR 0001 — Kafka is the durable event backbone

**Status:** Accepted

## Context
SignalChord requires replay, stable per-entity ordering, heterogeneous consumers, backpressure and operational visibility.

## Decision
Use Apache Kafka in KRaft mode with Schema Registry and Kafka Connect. Services use at-least-once consumption with idempotent effects; Kafka transactions are limited to consume-transform-produce operations that can atomically commit output and offsets.

## Consequences
Kafka topics and schemas are product contracts. External side effects still require inbox/outbox and idempotency records. Operational complexity is accepted because replay and streaming semantics are central product capabilities.
