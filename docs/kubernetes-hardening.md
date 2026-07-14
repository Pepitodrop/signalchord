# Kubernetes and Helm hardening

The SignalChord Helm chart deploys stateless application workloads only. Kafka, PostgreSQL, Neo4j, Redis, object storage, OpenSearch and telemetry backends must be operated externally by managed services or reviewed operators.

## Environment values

Use the environment overlays as starting points:

- `infrastructure/kubernetes/helm/signalchord/values-staging.yaml`
- `infrastructure/kubernetes/helm/signalchord/values-production.yaml`

Both overlays are credential-free. Secrets are sourced through the `ExternalSecret` defined in the chart and documented in `docs/secrets-and-transport.md`.

## Hardening controls

Rendered staging and production manifests must include:

- immutable `sha-*` image tags;
- non-root pod and container users;
- read-only root filesystems;
- dropped Linux capabilities;
- disabled privilege escalation and privileged mode;
- runtime default seccomp;
- service-account token automount disabled;
- per-workload service accounts;
- explicit requests and limits;
- resource quota;
- rolling-update bounds with `maxUnavailable: 0`;
- pod disruption budgets for replicated workloads;
- topology spread constraints;
- TLS ingress with an explicit host;
- deny-by-default NetworkPolicy plus DNS, internal, dependency and controlled public-ingress/egress rules.

The repository policy check is `scripts/validate_helm_policy.py`. CI renders staging and production manifests and runs this check. CI also creates a disposable kind cluster and validates that the rendered production manifests are accepted by kubectl dry-run syntax validation.

## External evidence still required

Issue #25 cannot be closed with repository evidence alone. Before production approval, attach:

- admission-controller results from the target cluster proving restricted Pod Security or equivalent policy enforcement;
- rendered staging and production manifests for the exact release candidate;
- NetworkPolicy connectivity tests proving default-deny behavior and allowed flows;
- ingress controller evidence showing TLS termination and host routing;
- capacity evidence supporting the configured requests, limits and ResourceQuota;
- an environment-specific decision on public internet egress CIDRs for ingestion/feed collection;
- a cluster install or server-side dry-run with the actual ExternalSecret CRDs and managed dependency namespaces installed.
