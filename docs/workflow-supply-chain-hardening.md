# Workflow supply-chain hardening

SignalChord treats CI/CD workflow dependencies as part of the release supply chain.

## Repository policy

- Third-party GitHub Actions must be pinned to immutable commit SHAs.
- Container actions must be pinned to complete `sha256` digests.
- Human-readable version comments may follow pinned references for maintenance clarity.
- Every workflow declares an explicit top-level permission map.
- Non-release workflows are read-only. The release workflow is read-only by default and grants write access only to the image-publishing and GitHub-release jobs that require it.
- The image-publishing job receives package, OIDC, and attestation write access; the final release job receives contents write access only.
- Checkout credentials should be disabled when later steps do not require authenticated Git operations.
- `scripts/validate_workflow_actions.py` enforces Action immutability and permission boundaries.

## Maintenance

When updating an Action:

1. Review the upstream release and security notes.
2. Resolve the desired tag to its exact commit SHA.
3. Replace the SHA and update the adjacent version comment.
4. Run `python3 scripts/validate_workflow_actions.py` and `python3 scripts/test_validate_workflow_actions.py`.
5. Require the complete CI, Workflow Security, and Source Snapshot workflows on the exact pull-request head before merge.

This control reduces exposure to mutable-reference compromise and overprivileged workflow tokens. It does not replace upstream Action review, GitHub environment protection, branch protection, or independent production release approval.
