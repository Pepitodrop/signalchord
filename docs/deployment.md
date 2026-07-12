# Deployment guide

## Environment model

Local Compose is a reproducible developer profile, not a production topology. Production separates stateless application deployments from Kafka, Neo4j, PostgreSQL, OpenSearch, Redis and object-storage stateful services. Prefer managed stateful services or dedicated operators with tested backup/restore.

## Build and provenance

- Build one immutable image per service from a protected commit.
- Generate SBOM and signed provenance; scan source, dependencies and image layers.
- Pin images by digest in production values.
- Generate Protobuf bindings and verify Schema Registry compatibility before promotion.
- Promote the same image digest through staging and production.

## Kubernetes/Helm

The chart under `infrastructure/kubernetes/helm/signalchord` deploys stateless SignalChord workers, gateway and web application. It expects externally provisioned Kafka/Schema Registry, Neo4j, PostgreSQL, Redis, object storage, OpenSearch and OpenTelemetry endpoints.

```bash
helm upgrade --install signalchord infrastructure/kubernetes/helm/signalchord \
  --namespace signalchord --create-namespace \
  --values values.production.yaml
```

Use a secret manager/CSI driver for credentials. The chart intentionally does not put secrets in values defaults.

## Kafka

Use at least three KRaft controllers and a replication factor appropriate to the durability target. Configure TLS/SASL, ACLs per producer/consumer, rack awareness, quotas, topic retention, DLQs, Schema Registry authentication and lag alerts. Run connector workers separately from brokers.

## Neo4j

Use Enterprise/AuraDB Enterprise when CDC is required. Apply constraints/migrations before enabling sink connectors. Scope connector credentials to required database privileges. Validate query/mutation latency and backup/restore before traffic.

## Rollout order

1. State stores and network/security policy.
2. Kafka topics and schema compatibility.
3. Neo4j schema and connector workers paused.
4. Rails migrations and control-plane API.
5. Idempotent consumers and projectors.
6. Connector enablement.
7. Gateway and clients.
8. Synthetic article-to-alert canary.

## Rollback

Roll back stateless images by digest. Do not roll back schemas or database migrations blindly: use forward-compatible event schemas, reversible application migrations and explicit graph migration compensation. Pause affected consumers/connectors before replay or repair.
