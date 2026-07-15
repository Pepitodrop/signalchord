# Workflow supply-chain hardening

SignalChord treats CI/CD workflow dependencies as part of the release supply chain.

## Repository policy

- Third-party GitHub Actions used by release and validation workflows must be pinned to immutable commit SHAs.
- Human-readable version comments may follow pinned SHAs for maintenance clarity.
- Release workflows use read-only permissions by default and elevate permissions only on the job that needs them.
- The release image-publishing job receives package, OIDC, and attestation write access; the final release job receives contents write access only.
- Checkout steps used for packaging or verification must not retain credentials unless a later step explicitly requires authenticated Git operations.
- `scripts/validate_workflow_actions.py` is the policy gate for workflow action references and release permission boundaries.

## Maintenance

When updating an Action:

1. Review the upstream release and security notes.
2. Resolve the desired tag to its exact commit SHA.
3. Replace the SHA and update the adjacent version comment.
4. Run `python3 scripts/validate_workflow_actions.py` and its tests.
5. Require the complete CI and source-snapshot workflows on the exact pull-request head before merge.

This control reduces exposure to mutable-tag compromise. It does not replace review of upstream Actions, GitHub environment protection, branch protection, or independent production release approval.
