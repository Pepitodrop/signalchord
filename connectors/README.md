# Kafka Connect

Connector configs are templates. Secrets are supplied through mounted config providers, never committed. CDC selectors include only graph changes required by analytics/realtime workflows. Every source event includes `origin=neo4j-cdc`; mutation builders reject events whose processing-stage chain already contains the target stage, preventing source/sink loops.

Replay: pause source connector, record CDC checkpoint, replay mutation topic with a dedicated group, verify idempotent MERGE results, resume from checkpoint and reconcile counts. Monitor task state, batch latency, retries, DLQ rate and Neo4j transaction latency.
