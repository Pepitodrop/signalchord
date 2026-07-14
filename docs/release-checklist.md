# Production release checklist

This checklist is the release gate for an internet-facing SignalChord deployment that handles real data. A green pull-request CI run is necessary but not sufficient. Every checked item must link to evidence for the exact release candidate.

## 1. Release identity and supply chain

- [ ] Release commit is protected, reviewed, and identified by full SHA.
- [ ] JavaScript, Go, Python, and Ruby dependencies are resolved from committed lock or checksum metadata using frozen/reproducible installs.
- [ ] Every application and third-party container image is referenced by digest.
- [ ] SBOMs exist for source dependencies and all shipped images.
- [ ] Source, dependency, secret-history, and final-image vulnerability scans have no unresolved critical finding.
- [ ] Images and provenance attestations are signed and verified before promotion.
- [ ] The same image digests were promoted from staging; production did not rebuild them.

Evidence:

- Release SHA:
- Image digest manifest:
- SBOM/provenance artifacts:
- Scan reports:
- Release procedure: `docs/release-supply-chain.md`

## 2. Data and source governance

- [ ] Every enabled source has a documented legal basis, attribution rule, retention requirement, deletion obligation, and responsible owner.
- [ ] Production allowlists prevent collection from unapproved sources and private/internal addresses.
- [ ] Data classification and regional storage requirements are documented.
- [ ] Retention, export, subject-access, correction, and deletion workflows were tested.
- [ ] Privacy and security review is approved for the intended deployment and customer type.

Evidence:

- Approved source inventory:
- Privacy/security review:
- Retention/deletion test:

## 3. Identity, secrets, and transport

- [ ] Production secrets come from an external secret manager or workload identity; no example credentials are deployed.
- [ ] Service identities follow least privilege and are unique per workload or trust boundary.
- [ ] Kafka uses TLS/SASL and explicit topic/group ACLs.
- [ ] PostgreSQL, Neo4j, Redis, OpenSearch, object storage, telemetry, APIs, and realtime connections use authenticated encrypted transport.
- [ ] Certificate and credential rotation was exercised.
- [ ] Authentication, account recovery, session invalidation, RBAC, and tenant isolation tests pass.

Evidence:

- Secret/identity architecture: `docs/secrets-and-transport.md`; Helm renders `ExternalSecret` and per-workload service accounts. External provider bindings and staging reconciliation logs still required.
- TLS and ACL verification:
- Authentication/tenant isolation report:

## 4. Infrastructure and Kubernetes

- [ ] Stateful services are externally operated with documented ownership and support expectations.
- [ ] Ingress, TLS, NetworkPolicies, workload identities, pod security settings, disruption budgets, and resource quotas are enabled.
- [ ] Images are immutable; privileged containers, host networking, and unnecessary capabilities are prohibited.
- [ ] Resource requests and limits are based on measured load.
- [ ] Autoscaling uses validated signals such as Kafka consumer lag and processing latency where appropriate.
- [ ] Environment-specific values contain no development endpoints, ports, credentials, or disabled security plugins.

Evidence:

- Rendered manifests and policy results:
- Kubernetes hardening evidence: `docs/kubernetes-hardening.md`; CI renders staging and production manifests, runs `scripts/validate_helm_policy.py`, and dry-runs production manifests in a disposable kind cluster.
- Infrastructure plan/change record:
- Capacity-based resource configuration:

## 5. Migrations, rollout, and rollback

- [ ] Database migrations were reviewed, backed up, and tested against a staging copy representative of production.
- [ ] Protobuf compatibility checks pass and event replay/migration notes exist for changed contracts.
- [ ] Neo4j constraints, search indexes, and topic setup are idempotent and verified.
- [ ] The synthetic article-to-alert canary passes in staging on the exact release images.
- [ ] A rollback exercise was completed without rebuilding artifacts.
- [ ] Forward-repair procedures exist for event/schema and irreversible migration changes.

Evidence:

- Migration run:
- Schema compatibility report:
- Staging canary:
- Rollback exercise:

## 6. Reliability and recovery

- [ ] RPO and RTO are defined for PostgreSQL, Kafka, Neo4j, Redis, object storage, OpenSearch, and application configuration.
- [ ] Backup and restore drills pass for authoritative data stores.
- [ ] OpenSearch and derived projections can be rebuilt from authoritative events/data.
- [ ] Consumer replay, poison-message handling, idempotency, and duplicate-delivery behavior are tested.
- [ ] Dependency outage, partial network failure, disk pressure, and restart scenarios were exercised.
- [ ] Disaster-recovery responsibilities and escalation paths are documented.

Evidence:

- Backup/restore report:
- Replay/rebuild report:
- Failure-injection report:

## 7. Performance and cost

- [ ] Representative load tests cover ingestion, NLP, graph/search projection, API queries, realtime clients, and notifications.
- [ ] Kafka lag, throughput, latency, error-rate, and saturation targets are documented.
- [ ] Rate limits, payload limits, concurrency bounds, and timeouts are configured and tested.
- [ ] Neo4j/OpenSearch/PostgreSQL capacity and index plans are supported by measurements.
- [ ] Expected infrastructure cost and per-tenant or per-document cost envelopes are approved.

Evidence:

- Load-test report:
- Capacity model:
- Cost model:

## 8. Observability and incident response

- [ ] Service-level indicators and objectives are defined for critical user and processing journeys.
- [ ] Dashboards cover availability, latency, errors, saturation, Kafka lag, queue age, delivery success, and data freshness.
- [ ] Alerts are actionable, routed to a named responder, and tested.
- [ ] Logs and traces use correlation identifiers without leaking secrets or sensitive content.
- [ ] Incident, security-event, data-quality, source-takedown, rollback, and disaster-recovery runbooks are available.
- [ ] An incident exercise or game day has been completed.

Evidence:

- SLO/dashboard links:
- Alert test:
- Game-day report:

## 9. Model and product quality

- [ ] Representative evaluation datasets are versioned with documented rights and provenance.
- [ ] Extraction, entity resolution, claim processing, and alerting meet approved precision/recall or equivalent targets.
- [ ] Bias, drift, false-positive, false-negative, and human-review thresholds are documented.
- [ ] Signup, onboarding, account administration, support, suspension, export, and deletion flows are complete.
- [ ] Email, mobile signing, push notifications, and billing/usage controls use production credentials and failure handling.

Evidence:

- Model-quality report:
- Product acceptance report:

## 10. Final approval

- [ ] All required GitHub checks are green on the exact release SHA.
- [ ] No unresolved critical security, privacy, legal, data-governance, or reliability finding exists.
- [ ] A named engineering owner, security/privacy owner, operations owner, and business owner accept the documented residual risks.

Approvals:

- Engineering:
- Security/privacy:
- Operations:
- Business/product:
- Release date and version:
