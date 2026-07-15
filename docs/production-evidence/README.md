# Production evidence directory

This directory is reserved for non-secret, reviewable evidence produced for a specific release candidate. Do not commit credentials, customer data, raw production exports, private penetration-test details, or provider secrets.

Evidence should identify the release tag, commit SHA, image digests, environment, execution time, responsible operator, command or runbook used, and the resulting pass/fail decision.

Use `template.md` and name committed records `evidence-<release>-<gate>.md` or `evidence-<release>-<gate>.json`. The directory allowlist intentionally rejects other filenames so accidental exports and arbitrary artifacts are not added without an explicit review decision.

Recommended evidence categories:

- target-cluster admission, NetworkPolicy, TLS, and pod-security validation;
- secret-manager and workload-identity binding verification;
- Kafka ACL and certificate-rotation exercises;
- load, cost, latency, and capacity results;
- backup, restore, replay, rollback, and RPO/RTO drills;
- dashboard, tracing, paging, and incident-exercise results;
- model-quality evaluation summaries and dataset provenance;
- legal, privacy, source-rights, customer-acceptance, and final risk approvals.

Large or sensitive evidence should remain in an approved external evidence store. Commit only a redacted manifest or durable reference that reviewers can verify.
