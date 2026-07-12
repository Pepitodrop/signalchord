# Contributing to SignalChord

Create focused branches and pull requests. Architectural, event-schema, graph-schema, source-policy, deployment and security changes require explicit review from their owners.

## Required checks

```bash
pnpm install --frozen-lockfile
pnpm typecheck && pnpm test && pnpm build
(cd services && go test -race ./...)
pytest -q services/nlp-pipeline services/entity-resolution services/claim-intelligence \
  services/velato-engine services/notification-worker services/graph-projector
buf lint packages/event-schemas
find scripts -type f -name '*.sh' -print0 | xargs -0 shellcheck
docker compose --profile slice config --quiet
helm lint infrastructure/kubernetes/helm/signalchord
```

Run `./scripts/dev-up.sh && ./scripts/smoke-test.sh` for changes that affect events, containers, graph projection, persistence, APIs or deployment wiring.

Every behavioral change includes tests, evidence/provenance implications, tenant-isolation review and documentation. Never commit credentials, source documents without explicit rights, generated customer data, model weights or production exports.

## Event changes

Preserve Protobuf field numbers, reserve removed fields, update the topic catalog and provide replay/migration notes. Breaking events require a new topic/schema major version.

## Graph changes

Use repeatable migrations and parameterized queries. Document stable-ID, tenant, temporal, confidence, status and provenance behavior. The graph projector accepts only an allowlisted mutation vocabulary.

## Definition of done

Acceptance criteria pass; CI is green on the exact commit; tests cover failure and replay; telemetry exists; security and governance impact is reviewed; dependency lockfiles and documentation are current.
