# Changelog

All notable SignalChord changes are documented here. The project follows semantic versioning from `v1.0.0` onward.

## [Unreleased]

No unreleased changes are recorded yet.

## [1.0.0] - 2026-07-16

### Added

- End-to-end article-to-alert reference pipeline.
- React analyst web interface and responsive mobile layouts.
- Expo mobile client with a securely stored, configurable self-hosted server URL.
- Rails control plane with tenant identity, RBAC, governed sources, watchlists, alerts, audit, onboarding, support and session APIs.
- Kafka ingestion and realtime services in Go.
- Python intelligence, graph/search projection, query, analytics, notification and Velato policy services.
- Docker Compose integration runtime and digest-pinned Kubernetes Helm charts.
- Single-owner, single-server k3s profile with PostgreSQL, Kafka, Neo4j Community, Valkey, MinIO, OpenSearch and local observability.
- Checksummed PostgreSQL and MinIO backup/restore tooling.
- Kubernetes acceptance validation and an optional repository-owned article-to-alert canary.
- Complete-history Gitleaks and proprietary-content publication audit with explicit ownership attestations.
- CI security scanning, SBOM generation, signed release-image workflow and provenance verification.
- Public-repository publication checklist, support policy, issue templates and release checklist.

### Changed

- Mobile sign-in no longer prefills development credentials.
- Community self-hosting requires no paid API subscription.
- Application images and release evidence use immutable SHA-256 digests.
- Kubernetes manifests are validated against Restricted Pod Security admission.
- Public API, application chart, web, mobile, API client and domain types report version `1.0.0`.

### Scope

`v1.0.0` is a public-source alpha and personal single-server Kubernetes reference. It is not a high-availability or multi-operator production service. Repository CI validates source, images, manifests and recovery tooling; an actual target-server restore drill, reboot recovery, mobile login and synthetic canary remain installation-specific operational evidence.

## [0.1.0-alpha] - Unreleased historical foundation

The pre-v1 foundation was never published as a Git tag. Its work is included in `v1.0.0`.
