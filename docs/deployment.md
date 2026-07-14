# Deployment guide

## Environment model

Docker Compose is the reproducible local-development and CI integration topology. It is not a production topology. Production separates stateless SignalChord workloads from Kafka, Neo4j, PostgreSQL, OpenSearch, Redis and object storage. Prefer managed services or dedicated operators with tested backup and restore procedures.

## Initial deployment units

The code remains modular, while the Helm chart consolidates processes with similar release and scaling characteristics:

1. Control-plane API.
2. Transactional outbox publisher.
3. Ingestion: document fetcher and stream normalizer.
4. Intelligence: NLP, entity resolution and claim intelligence.
5. Projection: first-party Neo4j graph projector and OpenSearch projector.
6. Graph-query API.
7. Graph analytics API and worker.
8. Alerting: policy API/worker, alert projector and notification worker.
9. Realtime gateway.
10. Web frontend.
11. Feed collection as a CronJob.

Split a process into its own deployment only when it requires different hardware, scaling, release cadence, availability or ownership. Do not create a new deployment merely because a source module exists.

## Build and provenance

- Build immutable images from a protected commit.
- Commit dependency lockfiles and use frozen installs.
- Generate an SBOM and signed provenance; scan source, dependencies and image layers.
- Pin production images by digest or a digest-backed immutable tag.
- Verify Protobuf compatibility before promotion.
- Promote the same image digest through staging and production.

The release workflow produces `release-manifest.json`, `image-digests.txt`,
SBOMs, vulnerability reports and Sigstore verification output. See
[Release supply chain](release-supply-chain.md) for the digest-only promotion
and verification procedure.

## Kubernetes/Helm

The chart under `infrastructure/kubernetes/helm/signalchord` deploys stateless application workloads. It expects externally provisioned Kafka/Schema Registry, Neo4j, PostgreSQL, Redis, object storage, OpenSearch and OpenTelemetry endpoints.

```bash
helm upgrade --install signalchord infrastructure/kubernetes/helm/signalchord \
  --namespace signalchord --create-namespace \
  --values values.production.yaml \
  --set global.imageTag=sha-<verified-commit>
```

Required production values include:

- an External Secrets Operator/CSI runtime secret source for `signalchord-runtime`;
- real service endpoints;
- an immutable image tag;
- environment-specific NetworkPolicy namespaces/CIDRs;
- ingress host, TLS secret and controller namespace;
- measured per-container resources.

The migration Job runs as a pre-install/pre-upgrade Helm hook. Review migrations before every release and use a dedicated least-privilege database identity.

See [Secrets, identities, and encrypted transport](secrets-and-transport.md) for required secret-store mappings, per-workload service accounts, Kafka ACL expectations, transport requirements and rotation evidence. Do not deploy production with local Compose credentials, plaintext service URLs or a manually created Kubernetes Secret that bypasses the managed secret store.

See [Kubernetes and Helm hardening](kubernetes-hardening.md) for environment overlays, manifest policy checks, restricted pod settings, NetworkPolicy expectations and the remaining cluster-side evidence required for issue #25.

## Autoscaling

HPA support is included but disabled. Enable it only after measurement. For Kafka workers, consumer lag and processing latency are generally more useful than CPU alone, and replica counts cannot usefully exceed relevant topic partitions.

## Kafka Connect

The verified local path uses the first-party graph projector. Kafka Connect is optional and lives under the `connect` Compose profile. Treat connector configuration as a separately tested integration; do not make core startup depend on a plugin downloaded at image-build time.

## Rollout order

1. Stateful dependencies, network policy and secrets.
2. Kafka topics and schema compatibility.
3. Neo4j constraints and search index preparation.
4. Database migration Job.
5. Control plane and outbox.
6. Idempotent consumers and projectors.
7. Query, alerting and realtime APIs.
8. Web ingress.
9. Synthetic article-to-alert canary.

## Rollback

Roll back stateless images by digest. Do not blindly reverse event schemas or database migrations. Pause affected consumers before replay or repair, preserve idempotency keys and use forward-compatible migrations.
