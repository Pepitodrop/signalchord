# Production readiness

## Decision

SignalChord is suitable for source publication and controlled development/staging use. It is **not yet approved for an internet-facing production service handling real customer data**.

The readiness decision must be based on evidence, not repository completeness. A green CI run proves the checked code and synthetic vertical slice; it does not prove capacity, availability, legal source rights or operational maturity.

## Execution and release evidence

- Track all remaining work in [GitHub issue #33](https://github.com/Pepitodrop/signalchord/issues/33).
- Use the [production release checklist](release-checklist.md) for the exact release candidate.
- Do not mark the project production-ready merely because individual implementation issues or CI jobs are complete. Operational drills, legal/privacy approvals, representative quality evidence, and named risk acceptance are required.

## Verified in CI

- TypeScript typecheck, tests and production builds.
- Go formatting, vet, race tests and vulnerability reachability checks.
- Python extraction, policy, notification and graph-projector tests.
- Rails database setup, request specs and autoload validation.
- Protobuf lint and compatibility checks.
- Shell, JSON, Compose and Helm rendering validation.
- Secret-history scanning and high/critical filesystem vulnerability scanning.
- Docker image builds for the implemented services.
- Synthetic end-to-end article-to-alert smoke test.

## Production blockers

The following are required before production approval:

1. **Licensed source inventory:** contracts, robots/terms review, attribution and deletion obligations for every source.
2. **Immutable supply chain:** committed dependency lockfiles, digest-pinned images, SBOMs, signed provenance and release promotion by digest.
3. **Managed secrets and transport security:** secret manager/CSI, Kafka TLS/SASL and ACLs, database TLS, certificate rotation and no example credentials.
4. **Data protection:** retention schedules, subject/deletion workflows, regional requirements and a completed privacy/security review.
5. **Capacity evidence:** realistic load tests, Kafka lag targets, Neo4j/OpenSearch sizing, rate limits and cost envelopes.
6. **Reliability evidence:** backup and restore drills, disaster-recovery objectives, dependency failure tests and rollback exercises.
7. **Observability:** production dashboards, actionable alerts, trace sampling, SLOs and on-call runbooks.
8. **Kubernetes hardening:** environment-specific NetworkPolicies, ingress/TLS, workload identities, immutable images, autoscaling based on measured signals and cluster policy enforcement.
9. **Model quality:** representative evaluation datasets, precision/recall targets, bias/error analysis and human-review thresholds.
10. **Product readiness:** completed authentication flows, customer onboarding, support process, billing controls and mobile signing/push credentials where applicable.

## Issue #24 repository progress

Repository-side controls for managed secrets and encrypted transport now include Helm `ExternalSecret` scaffolding, distinct Kubernetes service accounts per workload, Go/Python/Rails production-mode validators, Kafka TLS/SASL client configuration for Go/Python/Rails publishers, and OpenSearch certificate verification plus basic-auth support.

Issue #24 still requires external staging evidence before closure: real secret-store bindings, workload identity permission review, Kafka ACL allow/deny tests, certificate verification tests against managed dependencies, credential rotation, and provider audit logs.

## Issue #25 repository progress

Repository-side Kubernetes hardening includes credential-free staging and production values overlays, stricter restricted-container settings, rolling-update bounds, resource quota, rendered-manifest policy validation and disposable kind-cluster dry-run validation in CI.

Issue #25 still requires target-cluster evidence before closure: admission policy results, real ExternalSecret CRDs/controllers, NetworkPolicy connectivity tests, ingress TLS evidence and capacity measurements supporting requests, limits and quotas.

## Issue #29 repository progress

Repository-side application-security and tenant-isolation evidence includes expanded Rails tenant-negative request specs, tenant-scoped internal notification delivery updates, graph-query parameterization tests, search-projector tenant-index tests, realtime authorization tests, document-fetcher SSRF/redirect/timeout/size tests, Rack Attack body/auth/IP limits and API security headers.

Issue #29 still requires external production evidence before closure: independent penetration testing, ingress/WAF and load-balancer body/timeout validation, provider-side Kafka ACL tests, object-storage IAM tenant-prefix denial tests, managed data-store access reviews and formal disposition of any critical or high findings.

## Kubernetes position

The Helm chart deploys stateless application workloads in consolidated initial units. It intentionally does not deploy production Kafka, PostgreSQL, Neo4j, Redis, object storage or OpenSearch.

Autoscaling is disabled by default because CPU is not necessarily the correct scaling signal for Kafka consumers. Enable scaling only after measuring consumer lag, processing latency and partition constraints. KEDA or an equivalent custom-metric adapter is a likely later choice.

## Release gate

A release candidate may be promoted only when:

- required CI checks are green on the exact commit;
- images are immutable and scanned;
- `release-manifest.json` and the SBOM, scan and signature-verification artifacts from the release workflow are retained;
- migrations and synthetic canaries pass in staging;
- rollback and restore procedures have been exercised;
- no unresolved critical security or data-governance finding exists;
- a named owner accepts the remaining risks.
