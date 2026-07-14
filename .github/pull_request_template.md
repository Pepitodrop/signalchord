## Summary

Describe the change and why it is needed.

## Validation

- [ ] Tests cover the behavior and important failure paths.
- [ ] Required local checks or the equivalent CI jobs pass.
- [ ] Documentation is updated where behavior, configuration, or operations changed.
- [ ] No credentials, customer data, licensed source material, model weights, or production exports are included.

## Risk review

- [ ] Tenant isolation and authorization impact reviewed.
- [ ] Evidence, provenance, retention, and deletion impact reviewed.
- [ ] Event/schema compatibility and replay implications reviewed.
- [ ] Database or graph migrations are forward-compatible and have rollback/recovery notes.
- [ ] New external access is bounded by authentication, authorization, timeouts, size limits, and SSRF protections.
- [ ] Deployment changes use immutable artifacts and do not introduce development credentials or plaintext production transport.

## Release evidence

For production-affecting changes, link the exact staging run, synthetic canary, migration result, image digest/SBOM, and rollback or restore evidence. Use `N/A` only with a brief reason.
