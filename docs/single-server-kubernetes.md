# Single-server Kubernetes target

SignalChord `v1.0.0` targets one owner operating one Linux server for learning and personal use. The intended deployment uses Docker/container images, k3s or another conformant lightweight Kubernetes distribution, and the repository Helm chart.

A separate permanent staging server is not required. Pre-release validation may run in CI, a disposable local cluster and the target server before public network access is enabled.

## Intended topology

- One Linux server with persistent SSD storage.
- One Kubernetes control-plane/worker node.
- Stateless SignalChord workloads deployed through Helm.
- Community stateful services on the same server for the initial release: Apache Kafka, PostgreSQL, Neo4j Community, Valkey, MinIO and OpenSearch.
- Prometheus, Grafana OSS and OpenTelemetry for local observability.
- One ingress endpoint for the responsive web interface, control-plane API and realtime connection.
- Expo mobile client connecting to the same HTTPS endpoint.

This topology prioritizes reproducibility and learning. It does not provide high availability: failure of the server makes SignalChord unavailable until the node or backups are restored.

## Repository work required before deployment

1. Add a versioned single-node values overlay without credentials or host-specific paths.
2. Add manifests or documented Helm dependencies for the stateful community services.
3. Add local-path persistent-volume sizes and storage-class configuration.
4. Add a supported secret bootstrap process that creates secrets outside Git.
5. Add ingress configuration for same-origin web/API/realtime traffic.
6. Add installation, health, backup, restore, update and rollback scripts.
7. Add a clean k3s integration test where practical and retain existing disposable-cluster manifest validation.
8. Add a server acceptance script that runs migrations, initializes topics and constraints, and exercises the article-to-alert canary.

## Security baseline

- Only ingress and SSH are reachable from outside the server.
- Databases, Kafka, object storage, search and monitoring use ClusterIP services or localhost-only administration tunnels.
- Application images use exact release digests.
- Kubernetes workloads run without root, drop Linux capabilities and use the restricted security profile already enforced by the chart.
- Production credentials are generated uniquely and are not copied from Compose examples.
- HTTPS is required for access outside a trusted private network.
- Administrative dashboards are either disabled externally or protected by authentication and private networking.

## Backup baseline

The initial v1 backup contract is:

- PostgreSQL logical dump;
- Neo4j Community-compatible dump or documented offline volume backup;
- MinIO bucket backup;
- encrypted backup of configuration and secret material;
- documented rebuild procedure for OpenSearch and other derived projections;
- retention of the previous release digest values for rollback.

At least one restore and one immutable-digest rollback must succeed on the target server before the deployment is called operational.

## Mobile access

The Expo client stores the chosen API base URL in the operating system secure store. A public app-store release is not required. The operator may use Expo development builds, a locally built Android package, an iOS development build where available, or the responsive web interface on a phone.

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
- known limitations, especially the lack of high availability.
