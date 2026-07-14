# SignalChord agent instructions

These instructions apply to the entire repository unless a more specific `AGENTS.md` exists below the working directory.

## Repository intent

SignalChord is a public-alpha, multi-tenant news-intelligence platform. Treat provenance, tenant isolation, source rights, data deletion, replay safety, and operational evidence as first-class correctness requirements. Do not describe the repository or a hosted deployment as production-ready until the release gate in `docs/production-readiness.md` and `docs/release-checklist.md` is satisfied.

## Required reading

Before changing security, deployment, data handling, event contracts, graph persistence, authentication, or production behavior, read:

- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/production-readiness.md`
- `docs/release-checklist.md`
- `docs/deployment.md`
- `docs/threat-model.md`
- `docs/data-governance.md`

Use GitHub issue #33 as the production-readiness tracker. Work on one child issue per branch and pull request unless a dependency makes a narrowly documented combined change necessary.

## Change discipline

- Start from current `main` and verify the issue is still open and relevant.
- Keep changes focused; do not rewrite unrelated code or configuration.
- Preserve backward compatibility for Protobuf events, database migrations, graph schemas, and externally used APIs unless the issue explicitly authorizes a versioned breaking change.
- Prefer idempotent consumers, migrations, projectors, setup scripts, and recovery operations.
- Never commit secrets, production exports, customer data, unlicensed source documents, proprietary model weights, or generated credentials.
- Development credentials and plaintext local Compose endpoints must remain explicitly local-only.
- Do not weaken authentication, authorization, tenant scoping, SSRF controls, encryption, auditing, vulnerability gates, or data-governance checks to make tests pass.
- Record assumptions and incomplete external dependencies honestly. Do not mark legal review, penetration testing, backup drills, production capacity, or risk acceptance complete without real evidence.

## Validation

Run the narrowest relevant tests first, then the repository-required checks in `CONTRIBUTING.md`. For changes affecting events, containers, storage, APIs, graph/search projection, or deployment wiring, run the Docker Compose article-to-alert smoke test when the environment supports it.

Every behavioral change must include tests for normal behavior and meaningful failure/replay/tenant-boundary cases. Deployment changes must validate rendered manifests and must not introduce mutable production images, example credentials, localhost endpoints, disabled security plugins, or plaintext production transport.

## GitHub workflow

- Create a focused branch and pull request referencing the issue.
- Include the commands and results used for validation.
- Watch all GitHub checks on the exact head SHA and fix failures rather than bypassing or deleting gates.
- Do not force-push shared branches or overwrite unrelated work.
- Do not merge with failing, cancelled, stale, or still-running required checks.
- After merge, confirm the issue acceptance criteria and update the master tracker only when evidence supports completion.

## Production-readiness order

Default dependency order for issue #33:

1. Release supply chain (#23).
2. Secrets, identities, and encrypted transport (#24).
3. Kubernetes/Helm hardening (#25).
4. Application security and tenant isolation (#29).
5. Observability (#28).
6. Capacity and load validation (#27).
7. Backup, restore, replay, rollback, and disaster recovery (#26).
8. Data/source governance (#30), model quality (#31), and product operations (#32), which require both implementation and non-code evidence.

Parallelize only when branches do not overlap and the evidence dependencies remain clear.
