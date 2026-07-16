# Changelog

All notable SignalChord changes are documented here. The project follows semantic versioning once `v1.0.0` is published.

## [Unreleased]

## [1.0.0] - 2026-07-16

### Added

- End-to-end article-to-alert reference pipeline with responsive web and Expo mobile clients.
- Rails control plane, Kafka ingestion/realtime services, Python intelligence and graph/search projection services.
- Community-only self-hosting stack using Apache Kafka, PostgreSQL, Neo4j Community, Valkey, MinIO and OpenSearch.
- Digest-pinned single-owner k3s deployment profile with restricted pod security, ClusterIP-only stateful services and trusted TLS ingress.
- Encrypted single-server backup, checksum-verified restore and live Kubernetes article-to-alert acceptance tooling.
- Complete Git-history secret and proprietary-content audit with redacted CI evidence.
- Public repository governance, security reporting, contribution, support and publication documentation.
- Signed digest-addressed release images, SBOMs, vulnerability reports, provenance, checksums and release manifest generation.

### Changed

- Mobile sign-in accepts a self-hosted server URL, stores it securely and no longer prefills development credentials.
- The required community runtime uses no paid API subscription.
- Production and release Helm manifests require immutable application image digests.

### Known limitations

- The supported v1 deployment is one owner on one server and is not highly available.
- Community dependencies use plaintext transport only inside the documented single-node trust boundary; the Helm profile remains `staging` rather than a general multi-operator production profile.
- Kafka, OpenSearch and Valkey are treated as rebuildable transport, projection or cache state; authoritative backups cover PostgreSQL, Neo4j, MinIO and encrypted runtime configuration.
- A public app-store mobile release and commercial support are not included.

## [0.1.0-alpha] - Unreleased historical foundation

### Added

- End-to-end article-to-alert reference pipeline.
- React analyst web interface and Expo mobile client.
- Rails control plane with identity, tenant, RBAC, source, watchlist, alert, audit and session APIs.
- Kafka ingestion and realtime services in Go.
- Python intelligence, graph/search projection, query, analytics, notification and Velato policy services.
- Docker Compose integration runtime and Kubernetes Helm chart.
- CI, security scanning, SBOM generation, signed release images and provenance verification.

`0.1.0-alpha` is a documentation marker for the pre-v1 foundation and has not been published as a Git tag.
