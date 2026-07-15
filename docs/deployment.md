# Deployment guide

## Environment model

Docker Compose is the reproducible local-development and CI integration topology. It is not a production topology. Production separates stateless SignalChord workloads from Apache Kafka, Neo4j, PostgreSQL, OpenSearch, Valkey and object storage. These dependencies may be self-hosted with community software or operated by dedicated infrastructure with tested backup and restore procedures.

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
- Pin every production image by its verified `sha256` registry digest.
- Verify Protobuf compatibility before promotion.
- Promote the same image digest through staging and production.

The release workflow produces `release-manifest.json`, `image-digests.txt`,
SBOMs, vulnerability reports and Sigstore verification output. See
[Release supply chain](release-supply-chain.md) for the digest-only promotion
and verification procedure.

## Kubernetes/Helm

The chart under `infrastructure/kubernetes/helm/signalchord` deploys stateless application workloads. It expects externally provisioned Apache Kafka, Neo4j, PostgreSQL, Valkey, object storage, OpenSearch and OpenTelemetry endpoints. The verified path uses versioned Protobuf contracts and a first-party graph projector, so Schema Registry and Kafka Connect are not required.

Create a protected release-values file from the verified `image-digests.txt` artifact. The keys are the image names used by the chart, and values are registry digests—not tags:

```yaml
global:
  imageDigests:
    signalchord-control-plane: sha256:<verified-digest>
    signalchord-document-fetcher: sha256:<verified-digest>
    signalchord-stream-normalizer: sha256:<verified-digest>
    signalchord-python: sha256:<verified-digest>
    signalchord-realtime-gateway: sha256:<verified-digest>
    signalchord-web: sha256:<verified-digest>
    signalchord-feed-collector: sha256:<verified-digest>
```

Deploy the exact release candidate with both the environment overlay and the protected digest file:

```bash
helm upgrade --install signalchord infrastructure/kubernetes/helm/signalchord \
  --namespace signalchord --create-namespace \
  --values infrastructure/kubernetes/helm/signalchord/values-production.yaml \
  --values values.production.digests.yaml
```

Production rendering fails if any enabled image lacks a digest or supplies a value that does not match `sha256:` followed by 64 lowercase hexadecimal characters. Commit-SHA tags remain permitted for staging validation, but they are not accepted by the production manifest policy because registry tags can be moved.

Required production values include:

- an External Secrets Operator/CSI runtime secret source for `signalchord-runtime`;
- real service endpoints;
- verified image digests for every enabled image;
- environment-specific NetworkPolicy namespaces/CIDRs;
- ingress host, TLS secret and controller namespace;
- measured per-container resources.

The migration Job runs as a pre-install/pre-upgrade Helm hook. Review migrations before every release and use a dedicated least-privilege database identity.

See [Secrets, identities, and encrypted transport](secrets-and-transport.md) for required secret-store mappings, per-workload service accounts, Kafka ACL expectations, transport requirements and rotation evidence. Do not deploy production with local Compose credentials, plaintext service URLs or a manually created Kubernetes Secret that bypasses the managed secret store.

See [Kubernetes and Helm hardening](kubernetes-hardening.md) for environment overlays, manifest policy checks, restricted pod settings, NetworkPolicy expectations and the remaining cluster-side evidence required for issue #25.

## Autoscaling

HPA support is included but disabled. Enable it only after measurement. For Kafka workers, consumer lag and processing latency are generally more useful than CPU alone, and replica counts cannot usefully exceed relevant topic partitions.

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
