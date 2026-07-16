# Changelog

All notable SignalChord changes are documented here. The project follows semantic versioning once `v1.0.0` is published.

## [Unreleased]

### Added

- Configurable self-hosted server URL in the Expo mobile application.
- Public-repository publication checklist and single-server Kubernetes roadmap.
- Automated publication-readiness validation.

### Changed

- Mobile sign-in no longer prefills development credentials.
- The required community runtime uses Apache Kafka and Valkey and requires no paid API subscription.
- Production Helm manifests require immutable application image digests.

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
