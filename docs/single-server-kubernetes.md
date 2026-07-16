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

The repository contains:

- `infrastructure/kubernetes/helm/signalchord-community` for single-node community dependencies;
- `infrastructure/kubernetes/helm/signalchord/values-single-server.yaml` for one-replica application workloads;
- `scripts/single-server/render_digest_values.py` for release image evidence;
- `scripts/single-server/install.sh`, `health.sh`, `update.sh` and `rollback.sh` for lifecycle operations;
- `scripts/single-server/backup_restore.py` for checksummed PostgreSQL and MinIO backup and destructive restore;
- `scripts/single-server/acceptance.py` for cluster invariants and an optional synthetic article-to-alert canary;
- CI workflows for Helm rendering, Restricted Pod Security admission, recovery tooling and complete-history publication review.

Repository CI validates command behavior and Kubernetes admission. A real-server restore drill, reboot test, HTTPS/mobile login and synthetic canary must still be executed on the target server before that installation is described as operational.

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

Copy and protect the runtime template:

```bash
mkdir -p ~/.config/signalchord
cp infrastructure/kubernetes/single-server/runtime.env.example ~/.config/signalchord/runtime.env
chmod 600 ~/.config/signalchord/runtime.env
```

Install using exact release digests:

```bash
sh scripts/single-server/install.sh \
  --host signalchord.example.com \
  --digests ~/Downloads/image-digests.txt \
  --runtime-env ~/.config/signalchord/runtime.env \
  --yes
```

The installer refuses missing digest evidence, unsafe runtime-file permissions, a missing TLS Secret and an insufficient OpenSearch kernel setting.

## Updates and rollback

```bash
sh scripts/single-server/update.sh \
  --host signalchord.example.com \
  --digests ~/Downloads/image-digests-v1.0.1.txt \
  --runtime-env ~/.config/signalchord/runtime.env

helm -n signalchord history signalchord
sh scripts/single-server/rollback.sh --revision 2 --host signalchord.example.com
```

## Backup and restore

The automated backup covers the authoritative PostgreSQL database and the MinIO `raw-documents` bucket. It also records Helm values, non-secret cluster inventory, the Git SHA and SHA-256 checksums. Kubernetes Secret values are never exported; preserve the protected `runtime.env` separately in encrypted offline storage.

Use a reviewed MinIO client image pinned by digest:

```bash
python3 scripts/single-server/backup_restore.py backup \
  --namespace signalchord \
  --output /secure/backups/signalchord-$(date -u +%Y%m%dT%H%M%SZ) \
  --minio-client-image 'minio/mc@sha256:<verified-digest>'
```

The command suspends the feed collector and scales SignalChord application writers to zero for the maintenance window, then restores their previous state even when collection fails.

Restore is destructive and fails before mutation when a file or checksum is invalid:

```bash
python3 scripts/single-server/backup_restore.py restore \
  --namespace signalchord \
  --backup /secure/backups/signalchord-20260716T120000Z \
  --minio-client-image 'minio/mc@sha256:<verified-digest>' \
  --confirm-namespace signalchord \
  --yes
```

Kafka, Neo4j, OpenSearch, Valkey, Prometheus and Grafana are explicitly listed as not restored. They are operational or derived stores and require the replay/rebuild runbooks and acceptance testing after recovery.

## Kubernetes acceptance

Validate the cluster after installation, update, reboot or restore:

```bash
python3 scripts/single-server/acceptance.py \
  --namespace signalchord \
  --host signalchord.example.com
```

This checks Restricted Pod Security enforcement, required workloads, bound storage, digest-pinned application images, non-exposed internal Services, TLS ingress and required NetworkPolicies.

The optional synthetic canary uses credentials only through environment variables, creates a temporary repository-owned feed inside Kubernetes, triggers the collector, waits for a new alert and cleans up:

```bash
export SIGNALCHORD_ACCEPTANCE_EMAIL='owner@example.com'
export SIGNALCHORD_ACCEPTANCE_PASSWORD='<read-from-password-manager>'
export SIGNALCHORD_ACCEPTANCE_ORGANIZATION='your-organization-slug'

python3 scripts/single-server/acceptance.py \
  --namespace signalchord \
  --host signalchord.example.com \
  --canary \
  --fixture-image 'python@sha256:<verified-digest>'
```

Do not place acceptance credentials in command arguments, shell history or Git.

## Security boundary

- Only ingress and SSH may be reachable from outside the server.
- Databases, Kafka, object storage, search and monitoring are ClusterIP-only.
- Application images use exact release digests.
- Workloads use Restricted Pod Security and drop unnecessary capabilities.
- Runtime credentials are unique and are not copied from Compose examples.
- Trusted HTTPS is required for browser and mobile access.
- Grafana and other administrative services are not exposed by the charts.

The initial one-node dependency chart uses cluster-internal plaintext protocols and sets the application profile to `staging`, not `production`. This is acceptable only within the documented one-owner, one-node trust boundary. It is not suitable for untrusted workloads or multiple operators.

## Mobile access

The Expo client stores the selected API base URL in the operating-system secure store. A public app-store release is not required. A trusted HTTPS certificate is required for normal native access.

## Minimum operational evidence

Before calling a target-server installation operational, record:

- exact server OS, k3s, Helm and container-runtime versions;
- machine CPU, RAM and storage;
- immutable application image digests;
- successful Helm installation and pod health;
- successful login from desktop and phone;
- successful repository-owned article-to-alert canary;
- successful reboot recovery;
- successful checksummed backup and destructive restore drill during an isolated maintenance window;
- successful rollback to the preceding digest set;
- known limitations, especially no high availability, partial derived-store recovery and internal plaintext transport.
