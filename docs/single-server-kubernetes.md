# Single-server Kubernetes target

SignalChord `v1.0.0` targets a single-owner deployment on one Linux server for learning and personal use. The intended deployment uses Docker/container images, k3s or another conformant lightweight Kubernetes distribution, and repository-owned Helm charts.

A separate permanent staging server is not required. Pre-release validation runs in CI, a disposable cluster and the target server before public network access is enabled.

## Intended topology

- One Linux server with persistent SSD storage.
- One Kubernetes control-plane/worker node.
- Stateless SignalChord workloads deployed through the `signalchord` Helm chart.
- Community stateful services deployed through the `signalchord-community` Helm chart: Apache Kafka, PostgreSQL, Neo4j Community, Valkey, MinIO and OpenSearch.
- Prometheus, Grafana OSS and OpenTelemetry for local observability.
- One ingress endpoint for the responsive web interface, control-plane API and realtime connection.
- Expo mobile client connecting to the same HTTPS endpoint.

This topology prioritizes reproducibility and learning. It does not provide high availability: failure of the server makes SignalChord unavailable until the node or backups are restored.

## Current repository support

The repository now contains:

- `infrastructure/kubernetes/helm/signalchord-community` for single-node community dependencies;
- `infrastructure/kubernetes/helm/signalchord/values-single-server.yaml` for one-replica application workloads;
- `scripts/single-server/render_digest_values.py` for converting release image evidence into Helm values;
- `scripts/single-server/install.sh` for idempotent installation;
- `scripts/single-server/health.sh` for workload, storage and HTTPS verification;
- `scripts/single-server/update.sh` and `rollback.sh` for immutable upgrades and Helm revision rollback;
- a dedicated CI workflow that lints and renders both charts and validates them in a disposable cluster.

Backup and restore automation, a real-server acceptance canary and encrypted internal dependency transport remain required before the target server should be described as operational v1.

## Prerequisites

The target server needs:

- a supported Linux distribution;
- k3s or another Kubernetes distribution;
- `kubectl`, Helm 3, Python 3 and `curl`;
- a default `local-path` storage class or an explicit replacement in community values;
- `vm.max_map_count=262144` or higher for OpenSearch;
- a trusted TLS certificate and key for the chosen hostname;
- the `image-digests.txt` artifact from a successful SignalChord release;
- a runtime environment file created outside Git from `infrastructure/kubernetes/single-server/runtime.env.example`.

The runtime file must contain unique values, remain outside the repository and use mode `0600`.

## Installation

Create the namespace and trusted ingress certificate:

```bash
kubectl create namespace signalchord
kubectl -n signalchord create secret tls signalchord-ingress-tls \
  --cert /secure/path/fullchain.pem \
  --key /secure/path/private-key.pem
```

Copy the runtime template outside the repository, replace every placeholder and protect it:

```bash
mkdir -p ~/.config/signalchord
cp infrastructure/kubernetes/single-server/runtime.env.example \
  ~/.config/signalchord/runtime.env
chmod 600 ~/.config/signalchord/runtime.env
```

Install using the exact signed release digests:

```bash
sh scripts/single-server/install.sh \
  --host signalchord.example.com \
  --digests ~/Downloads/image-digests.txt \
  --runtime-env ~/.config/signalchord/runtime.env \
  --yes
```

The installer refuses missing digest evidence, insecure runtime-file permissions, a missing TLS Secret and an insufficient OpenSearch kernel setting. It applies the runtime Secret, installs community dependencies, initializes Kafka topics and the private MinIO bucket, deploys SignalChord by digest and runs health checks.

## Updates and rollback

Update to another release using its new `image-digests.txt` artifact:

```bash
sh scripts/single-server/update.sh \
  --host signalchord.example.com \
  --digests ~/Downloads/image-digests-v1.0.1.txt \
  --runtime-env ~/.config/signalchord/runtime.env
```

Review available revisions and roll back without rebuilding images:

```bash
helm -n signalchord history signalchord
sh scripts/single-server/rollback.sh \
  --revision 2 \
  --host signalchord.example.com
```

## Security boundary

- Only ingress and SSH may be reachable from outside the server.
- Databases, Kafka, object storage, search and monitoring are ClusterIP-only.
- Application images use exact release digests.
- Workloads use restricted pod security and drop unnecessary capabilities where supported.
- Runtime credentials are unique and are not copied from Compose examples.
- Trusted HTTPS is required for normal browser and mobile access.
- Grafana and other administrative services are not exposed by the charts.

The initial single-node dependency chart uses cluster-internal plaintext protocols and sets the application profile to `staging`, not `production`. This is acceptable only within the documented one-owner, one-node trust boundary. Encrypted Kafka, MinIO, Valkey, Neo4j and OpenSearch transport remains a v1 hardening task before exposing the cluster to untrusted workloads or operators.

## Backup baseline

The initial v1 backup contract is:

- PostgreSQL logical dump;
- Neo4j Community-compatible offline dump or volume backup;
- MinIO bucket backup;
- encrypted backup of configuration and secret material;
- documented rebuild procedure for Kafka, OpenSearch and other derived projections;
- retention of previous release digest values and Helm revision history.

At least one restore and one immutable-digest rollback must succeed on the target server before the deployment is called operational.

## Mobile access

The Expo client stores the chosen API base URL in the operating-system secure store. A public app-store release is not required. The operator may use Expo development builds, a locally built Android package, an iOS development build where available, or the responsive web interface on a phone. A trusted HTTPS certificate is required for normal native mobile access.

## Minimum release evidence

Before tagging `v1.0.0`, record:

- exact server OS, k3s, Helm and container-runtime versions;
- machine CPU, RAM and storage;
- immutable application image digests;
- successful Helm installation and pod health;
- successful login from desktop and phone;
- successful permitted-feed article-to-alert canary;
- successful reboot recovery;
- successful backup restore;
- successful rollback to the preceding digest set;
- known limitations, especially the lack of high availability and internal transport encryption.
