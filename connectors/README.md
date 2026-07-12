# Optional Kafka Connect integrations

The verified local and initial Kubernetes paths use the first-party `services/graph-projector` for Kafka-to-Neo4j mutation projection. Kafka Connect is optional and is isolated behind the Compose `connect` profile.

Connector configurations in this directory are interoperability templates, not release-gated production defaults. Before enabling one, validate the exact Kafka Connect, converter, Neo4j server and plugin versions; verify payload shape against the connector documentation; run replay/idempotency tests; and define retry, DLQ and credential-rotation procedures.

Secrets must be supplied through an external secret/config provider and must never be committed. CDC, where licensed and supported by the selected Neo4j edition, should publish only explicitly approved graph changes and must include loop-prevention metadata.

For a connector replay: pause the connector, record its checkpoint, replay through a dedicated consumer group, reconcile idempotent results, then resume from the recorded checkpoint. Monitor task state, batch latency, retry/DLQ rate and Neo4j transaction latency.
