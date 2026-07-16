# Public repository publication checklist

This checklist covers publishing SignalChord as a personal open-source project. It is deliberately narrower than operating a public multi-user SaaS service.

## Repository content

- [ ] `README.md` accurately describes implemented and incomplete features.
- [ ] `LICENSE`, `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md` and `CHANGELOG.md` are present.
- [ ] Installation, backup, restore, Kubernetes acceptance and mobile connection instructions are reproducible.
- [ ] Only repository-owned or redistributable fixtures, screenshots, icons, fonts and datasets are committed.
- [ ] No internship, employer, customer or other proprietary material is present.
- [ ] Generated files, local state, backups, age identities and secrets are excluded by `.gitignore`.

## Security and privacy

- [ ] `Repository History Audit` passes against the complete Git history on the exact release commit.
- [ ] Gitleaks reports no private key, token, password, cookie or production credential in any reachable Git object.
- [ ] The proprietary-content audit reports no blocked historical path, confidentiality marker or private hashed denylist term.
- [ ] No production URL or personal data remains in current files or history.
- [ ] Example credentials are clearly limited to local development and are never used by the Kubernetes deployment.
- [ ] Security reporting through `SECURITY.md` is reachable before the repository becomes public.
- [ ] Public fixtures contain synthetic data and do not identify private people.

## Licensing

- [ ] SignalChord-owned code remains Apache-2.0.
- [ ] `NOTICE` lists separately licensed runtime components.
- [ ] The community stack requires no paid API or commercial service.
- [ ] Dependency and container-image licence reports have been reviewed for the release candidate.
- [ ] Any AGPL/GPL services remain separate services and retain their notices.

## Product, recovery and mobile surfaces

- [ ] The responsive web interface works at phone, tablet and desktop widths.
- [ ] The Expo mobile client accepts a self-hosted server URL and stores it securely.
- [ ] Neither web nor mobile sign-in prefills development credentials in a release build.
- [ ] Mobile builds, type checks and navigation tests pass.
- [ ] Screenshots reflect the current UI and contain no real credentials or private data.
- [ ] A backup completes with encrypted runtime configuration and valid SHA-256 checksums.
- [ ] A destructive restore drill succeeds on a clean installation of the exact release digests.
- [ ] Strong Kubernetes acceptance creates a new article-to-alert result after restore.

## Automation and release

- [ ] Required CI, security, community-stack, workflow-security, Helm, source-snapshot, repository-history and publication-readiness checks pass on the exact release commit.
- [ ] The release workflow produces signed digest-addressed images, SBOMs, vulnerability reports, provenance, checksums and a release manifest.
- [ ] `v1.0.0` release notes list supported deployment scope, known limitations and upgrade/rollback instructions.
- [ ] `main` is protected and pull requests require successful checks.
- [ ] Dependabot is configured according to `docs/dependency-maintenance.md`: compatible routine updates remain small, security updates stay enabled, and major upgrades use dedicated migration PRs.
- [ ] Dependency PRs pass full CI and deployment validation rather than being merged only because they are automated.

## GitHub publication settings

The repository owner must complete these settings manually because they are account-level decisions:

- [ ] Enable private vulnerability reporting.
- [ ] Configure branch protection or a ruleset for `main`.
- [ ] Confirm GitHub Actions and GHCR package visibility.
- [ ] Add repository description, topics, social preview and homepage URL where applicable.
- [ ] Change repository visibility from private to public only after all current-history checks pass.

Publication approval means the source is ready to be public. It does not claim that an arbitrary internet deployment is secure or supported.
