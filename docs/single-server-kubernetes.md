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
- `scripts/single-server/render_digest_values.py` for converting release image evidence into Helm values;
- `scripts/single-server/install.sh` for idempotent installation;
- `scripts/single-server/health.sh` for workload, storage and HTTPS verification;
- `scripts/single-server/backup.sh`, `backup-postgres-only.sh` and `restore.sh` for encrypted, checksum-verified recovery;
- `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml` for scheduled, in-cluster automation of both backup cadences;
- `scripts/single-server/acceptance.sh` for a live permitted-feed article-to-alert canary;
- `scripts/single-server/update.sh` and `rollback.sh` for immutable upgrades and Helm revision rollback;
- dedicated CI that lints and renders both charts, validates restricted admission, checks the operations scripts and audits complete repository history.

Internal dependency transport is plaintext inside the single-node cluster. The profile therefore remains `staging`, not a general multi-operator production profile.

## Prerequisites

The target server needs:

- a supported Linux distribution;
- k3s or another Kubernetes distribution;
- `kubectl`, Helm 3, Python 3, `curl`, `age`, `tar`, `sha256sum` and the MinIO client (`mc`);
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

## Kubernetes acceptance

Create a token file outside Git containing one valid bearer token on its first line and protect it with mode `0600`. The deployment must already contain at least one permitted source and one watchlist.

```bash
sh scripts/single-server/acceptance.sh \
  --host signalchord.example.com \
  --token-file ~/.config/signalchord/acceptance.token
```

The acceptance script verifies both Helm releases, workload and PVC health, authenticated source/watchlist/alert APIs, a one-off feed-collector Job and a new durable alert. `--allow-existing-alert` weakens the canary and is intended only for troubleshooting an unchanged source; it is not valid `v1.0.0` release evidence.

## Encrypted backup

Generate an age identity outside Git and retain its private key separately from the server backup:

```bash
age-keygen -o ~/.config/signalchord/backup.agekey
age-keygen -y ~/.config/signalchord/backup.agekey
```

Use the printed public recipient to create a backup directory outside the repository, mirrored into a dedicated destination MinIO bucket (distinct from the application's own document bucket) via access-key/secret-key files:

```bash
sh scripts/single-server/backup.sh \
  --output /srv/backups/signalchord-$(date +%Y%m%d-%H%M%S) \
  --runtime-env ~/.config/signalchord/runtime.env \
  --age-recipient age1example... \
  --dest-minio-endpoint backup-object-storage.example.com:9000 \
  --dest-minio-bucket signalchord-backups-full \
  --dest-minio-access-key-file ~/.config/signalchord/backup-minio-access-key \
  --dest-minio-secret-key-file ~/.config/signalchord/backup-minio-secret-key \
  --yes
```

The backup operation temporarily suspends feed collection and scales application deployments to zero so no repository-owned workload can mutate authoritative data during the snapshot. It then creates a PostgreSQL custom-format dump, offline Neo4j Community dumps for both the `neo4j` and `system` databases, an offline MinIO volume archive, encrypted runtime configuration, Helm release evidence, Kubernetes resource metadata, Kafka topic metadata, OpenSearch index inventory and SHA-256 checksums. MinIO and Neo4j are restarted before application replicas and the prior CronJob suspension state are restored, and the completed directory is mirrored to the destination bucket.

Kafka, OpenSearch and Valkey are treated as rebuildable projections or transport/cache state rather than authoritative backup data. Copy the completed directory to storage that is not on the same physical server. A backup is not accepted until a restore drill succeeds.

Because this full backup requires scaling the application to zero for the MinIO/Neo4j snapshot, it runs on a longer cadence (daily by default via `backup-cronjob.yaml`) than the 15-minute PostgreSQL recovery-point objective requires. `scripts/single-server/backup-postgres-only.sh` closes that gap: `pg_dump` takes an MVCC-consistent snapshot of a live database, so this lightweight script never suspends feed collection or scales any deployment, and it uploads directly to its own dedicated bucket instead of a local directory:

```bash
sh scripts/single-server/backup-postgres-only.sh \
  --runtime-env ~/.config/signalchord/runtime.env \
  --age-recipient age1example... \
  --minio-endpoint backup-object-storage.example.com:9000 \
  --minio-bucket signalchord-backups-postgres-only \
  --minio-access-key-file ~/.config/signalchord/backup-minio-access-key \
  --minio-secret-key-file ~/.config/signalchord/backup-minio-secret-key \
  --yes
```

Both cadences are automated in-cluster by `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml` (`backup.postgresOnly.schedule`, default every 15 minutes, and `backup.full.schedule`, default daily), reconstructing the runtime environment from the `signalchord-runtime` Secret and reading destination MinIO credentials from `backup.destinationSecretName`.

## Restore drill

Install the same digest-addressed release into the target namespace before restoring, and annotate that namespace `signalchord.io/restore-target: allowed` — `restore-v1.sh` refuses to run against any namespace lacking that exact annotation, regardless of its name or `SIGNALCHORD_ENV` label. The restore operation is destructive: application deployments are stopped, PostgreSQL is replaced, MinIO is cleared and loaded (unless `--postgres-only` is used), both Neo4j databases are loaded offline (unless `--postgres-only` is used), and workloads are restarted only after successful restoration.

```bash
kubectl annotate namespace signalchord-restore-drill signalchord.io/restore-target=allowed

sh scripts/single-server/restore.sh \
  --backup /srv/backups/signalchord-20260716-180000 \
  --host signalchord.example.com \
  --age-identity ~/.config/signalchord/backup.agekey \
  --namespace signalchord-restore-drill \
  --confirm-context "$(kubectl config current-context)" \
  --smtp-blackhole-host smtp-blackhole.invalid \
  --expo-blackhole-url https://expo-blackhole.invalid/push \
  --yes
```

The stable `restore.sh` entrypoint dispatches to the versioned format implementation. It verifies every checksum, required artifact, authoritative data-set declaration, quiesced-snapshot marker (skipped for `--postgres-only` backups, which are never quiesced) and runtime-file permission before changing the cluster. It also requires the operator (or an automated drill) to retype the exact `kubectl config current-context` value as `--confirm-context`, refusing to proceed on any mismatch. Before the application is scaled back up, it overrides `SMTP_HOST` and `EXPO_PUSH_URL` in the restored runtime Secret to the supplied black-hole values so a restored environment cannot send real customer email or push notifications. Add `--postgres-only` to restore from a `backup-postgres-only.sh` snapshot (PostgreSQL-corruption-only scenario; requires a manifest containing only `{postgresql, runtime-config}`). On failure, application deployments remain stopped for inspection. After success, run the strong acceptance canary and verify that Kafka/OpenSearch projections rebuild from authoritative data.

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
- Backups encrypt runtime secret material and must be stored off-server with restrictive permissions.

The initial single-node dependency chart uses cluster-internal plaintext protocols and sets the application profile to `staging`, not `production`. This is acceptable only within the documented one-owner, one-node trust boundary. Encrypted Kafka, MinIO, Valkey, Neo4j and OpenSearch transport remains required before exposing the cluster to untrusted workloads or operators.

## Mobile access

The Expo client stores the chosen API base URL in the operating-system secure store. A public app-store release is not required. The operator may use Expo development builds, a locally built Android package, an iOS development build where available, or the responsive web interface on a phone. A trusted HTTPS certificate is required for normal native mobile access.

## Minimum release evidence

Before tagging `v1.0.0`, record:

- exact server OS, k3s, Helm and container-runtime versions;
- machine CPU, RAM and storage;
- immutable application image digests;
- successful exact-commit CI and complete-history audit;
- successful Helm installation and pod health;
- successful login from desktop and phone;
- successful permitted-feed article-to-alert acceptance without `--allow-existing-alert`;
- successful reboot recovery;
- successful quiesced backup restore, including Neo4j `system`, and post-restore acceptance;
- successful rollback to the preceding digest set;
- known limitations, especially the lack of high availability and internal transport encryption.
