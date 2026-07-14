# Secrets, identities, and encrypted transport

SignalChord production deployments must not use repository literals, local Compose credentials, plaintext service URLs, or shared infrastructure identities. The Helm chart renders an `ExternalSecret` named `signalchord-runtime` and injects that Kubernetes Secret with `envFrom`. The Secret must be reconciled by External Secrets Operator or an equivalent CSI/external-secret controller from a managed secret store.

## Required runtime secrets

| Environment key | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL URL with `sslmode=require` or `sslmode=verify-full`. |
| `SECRET_KEY_BASE` | Rails secret, at least 64 characters. |
| `CONTROL_PLANE_INTERNAL_TOKEN` | Internal API token, at least 32 characters. |
| `NOTIFICATION_TOKEN_ENCRYPTION_KEY` | Notification-token encryption key, at least 32 characters. |
| `KAFKA_SASL_USER` / `KAFKA_SASL_PASSWORD` | Kafka client identity credentials. |
| `KAFKA_TLS_CA_PEM` | Kafka CA bundle when the platform CA is not sufficient. |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Object-storage identity. |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Graph database identity. |
| `OPENSEARCH_USERNAME` / `OPENSEARCH_PASSWORD` | Search identity. |

The default chart remote references are placeholders under `signalchord/...`. Platform owners must map them to the real provider paths and bind the external-secret controller to a read-only secret-store identity.

## Workload identities

The chart creates a distinct Kubernetes service account for every workload.

| Workload | Kubernetes service account | Minimum permissions |
| --- | --- | --- |
| `control-plane` | `signalchord-control-plane` | Read runtime secret; connect to PostgreSQL, Redis, Kafka, OpenSearch, and telemetry. |
| `outbox` | `signalchord-outbox` | Read runtime secret; publish authorized Kafka topics; connect to PostgreSQL. |
| `ingestion` | `signalchord-ingestion` | Read runtime secret; consume discovery/fetched topics; write object storage; publish normalization topics. |
| `intelligence` | `signalchord-intelligence` | Read runtime secret; consume NLP/entity/claim topics; publish graph and alert-request topics; read object storage. |
| `projection` | `signalchord-projection` | Read runtime secret; consume projection topics; write Neo4j/OpenSearch; read object storage. |
| `graph-query` | `signalchord-graph-query` | Read runtime secret; read Neo4j. |
| `graph-analytics` | `signalchord-graph-analytics` | Read runtime secret; read/write graph analytics topics; read Neo4j/GDS. |
| `alerting` | `signalchord-alerting` | Read runtime secret; consume policy/notification topics; call control-plane internal APIs. |
| `realtime` | `signalchord-realtime` | Read runtime secret; consume realtime topics; call control-plane token introspection. |
| `web` | `signalchord-web` | No secret access unless deployment-specific telemetry requires it. |
| `feed-collector` | `signalchord-feed-collector` | Read runtime secret; publish discovery topic only. |
| `migration` | `signalchord-migration` | Read runtime secret; apply database migrations with a reviewed migration database role. |

Use `serviceAccount.workloadAnnotations` to bind each service account to the cloud workload identity for the target platform, for example AWS IRSA, GKE Workload Identity, or Azure Workload Identity.

## Kafka ACLs

Kafka must require TLS and SASL. Runtime checks reject `SIGNALCHORD_ENV=production` unless `KAFKA_TLS_ENABLED=true`, `KAFKA_SASL_ENABLED=true`, and SASL credentials are present.

Required external evidence for issue #24: a staging ACL test must prove allowed publish/consume paths succeed and unauthorized cross-topic or cross-tenant paths are denied for each identity.

## Transport requirements

Production runtime validation rejects local addresses, known development credentials, and plaintext URL schemes for Kafka, PostgreSQL, Redis, Neo4j, OpenSearch, object storage, control-plane internal calls, and browser origins. The chart defaults use Kafka TLS/SASL, Redis `rediss://`, Neo4j `neo4j+s://`, OpenSearch `https://` with certificate verification and basic auth, object storage with `MINIO_SECURE=true`, and HTTPS internal API/telemetry URLs.

If the cluster uses service-mesh mTLS instead of application-native TLS for internal HTTP services, platform owners must supply mesh configuration and staging evidence showing certificate verification, peer identity enforcement, and fail-closed behavior before marking the release gate complete.

## Rotation

Credential and certificate rotation must be exercised in staging:

1. Add the next credential or certificate version to the managed secret store.
2. Confirm `ExternalSecret` reconciles `signalchord-runtime`.
3. Restart one replica per workload and verify readiness.
4. Roll all replicas.
5. Revoke the previous credential.
6. Run the article-to-alert smoke test and Kafka ACL denial checks.
7. Attach timestamps, command output, and provider audit log references to issue #24.

Do not close issue #24 without staging rotation evidence and explicit platform owner confirmation that no service-wide data loss occurred.
