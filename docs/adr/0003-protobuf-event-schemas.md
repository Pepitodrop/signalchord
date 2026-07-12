# ADR 0003 — Protobuf schemas with a shared envelope

**Status:** Accepted

## Decision
Use Protobuf and Schema Registry for Kafka event contracts. A common envelope carries version, tenant, event/source time, correlation, causation, origin, stage, idempotency and tracing metadata.

## Consequences
Field numbers are never reused; removal reserves fields; compatibility tests are mandatory. JSON may be used for local inspection but is not the long-term wire contract.
