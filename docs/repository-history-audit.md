# Repository history publication audit

SignalChord must pass a complete-history audit before repository visibility changes from private to public or a stable release tag is created.

## Automated scope

The `Repository History Audit` workflow checks every reachable Git commit and blob with `fetch-depth: 0`.

- Gitleaks scans the complete Git history with findings redacted.
- `scripts/audit_repository_history.py` examines historical file paths, blob contents and commit messages.
- High-risk historical paths include environment files, private keys, credential files, backup/database artifacts and Terraform state.
- Blob contents are checked for private-key material, common live-token formats and strong confidentiality or distribution-restriction markers.
- A private source-term list is stored only as lowercase SHA-256 hashes with byte lengths. This allows known employer, customer, infrastructure and personal-data markers to be detected without publishing the source terms.
- Regression tests prove that deleted secrets and hashed private terms remain detectable through history.

The workflow uploads redacted JSON evidence for the exact commit under test. Any finding blocks publication; the repository history must be rewritten or the material removed from every reachable ref before retrying. Findings must not be allowlisted merely because the current tree is clean.

## Manual ownership review

Before publication, the owner must also verify that current and historical fixtures, screenshots, icons, fonts, datasets, copied snippets and generated artifacts are either SignalChord-owned or redistributable under their included licences. In particular, no employer, internship, customer or private infrastructure material may be present.

## Release evidence

For `v1.0.0`, retain:

1. the successful `Repository History Audit` workflow URL and artifact for the exact tagged commit;
2. the successful full CI, workflow-security, source-snapshot, publication-readiness and single-server-k3s checks;
3. confirmation that private vulnerability reporting and `main` branch protection are enabled;
4. confirmation that GHCR packages intended for self-hosting are public or otherwise accessible to the target server.

Changing visibility is an account-level action and must happen only after these checks pass. A public repository does not by itself make an internet deployment secure.
