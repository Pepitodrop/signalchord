# Contributing to SignalChord

Create focused branches and pull requests. Architectural, event-schema, graph-schema, source-policy and security changes require explicit review from their owners.

## Required checks

```bash
pnpm typecheck && pnpm test && pnpm build
(cd services && go test -race ./...)
pytest -q services/nlp-pipeline services/velato-engine
buf lint packages/event-schemas
shellcheck scripts/*.sh
docker compose config --quiet
```

Every behavioral change includes tests, evidence/provenance implications, tenant-isolation review and documentation. Never commit credentials, source documents without explicit rights, generated customer data, model weights or production exports.

## Event changes

Preserve Protobuf field numbers, reserve removed fields, update the topic catalog and provide replay/migration notes. Breaking events require a new topic/schema major version.

## Graph changes

Use repeatable migrations and parameterized queries. Document stable-ID, tenant, temporal, confidence, status and provenance behavior.

## Definition of done

Acceptance criteria pass; CI is green; tests cover failure/replay; telemetry exists; security/governance impact is reviewed; docs and ClickUp state are current.
