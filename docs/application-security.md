# Application security and tenant isolation

SignalChord is a multi-tenant system. Production readiness requires evidence that public APIs, internal service APIs, ingestion, graph/search projections and realtime delivery fail closed when a tenant identifier, bearer token or source URL is malicious or stale.

This page records repository-side controls and the external evidence still required for GitHub issue #29.

## Trust boundaries and controls

| Boundary | Control | Automated evidence |
|---|---|---|
| Public Rails API | Bearer API token authentication, token expiry/revocation checks, organization-scoped ActiveRecord lookups, role/scope checks on writes | `apps/control-plane/spec/requests/tenant_isolation_spec.rb` |
| Search API to OpenSearch | Rails builds a server-side OpenSearch query with `tenant_id` from the authenticated organization and ignores client-supplied tenant IDs | `apps/control-plane/spec/requests/tenant_isolation_spec.rb` |
| Graph API to graph-query service | Rails overwrites graph proxy `tenant_id` with the authenticated organization; graph-query uses parameterized Cypher with tenant predicates | `apps/control-plane/spec/requests/tenant_isolation_spec.rb`, `services/graph-query/test_app.py` |
| Search projection | Indexed document IDs are tenant-prefixed and indexed bodies carry `tenant_id` fields used by API filters | `services/search-projector/test_worker.py` |
| Graph projection | Graph nodes and relationship endpoints are merged with tenant identity as part of the Neo4j key | `services/graph-projector/test_worker.py` |
| Realtime delivery | Production requires bearer-token introspection; broker publishes only to subscribers for the event tenant and bounds slow consumers | `services/realtime-gateway/main_test.go` |
| Internal notification delivery updates | Internal calls must provide `tenant_id`; delivery updates are scoped through that organization | `apps/control-plane/spec/requests/tenant_isolation_spec.rb` |
| Document fetching | HTTP(S)-only URL policy, exact private-host allowlist, per-hop redirect validation, private-address dial checks, response-header timeout and response-size limit | `services/document-fetcher/policy_test.go`, `services/document-fetcher/cmd/main_test.go` |
| Public interface abuse | Rack Attack IP throttles, stricter auth throttle, API body-size block, response security headers, production CORS/HTTPS validation | `apps/control-plane/config/initializers/rack_attack.rb`, `apps/control-plane/spec/requests/tenant_isolation_spec.rb`, `apps/control-plane/spec/lib/production_config_spec.rb` |

## Production configuration

Production mode must continue to reject local/plaintext defaults through the validators added for issue #24. Relevant application-security settings:

- `WEB_ORIGINS` must contain only HTTPS origins.
- `FORCE_SSL=true` is required for the control plane.
- `API_RATE_LIMIT`, `AUTH_RATE_LIMIT` and `API_MAX_BODY_BYTES` may be lowered per environment after load testing.
- `CONTROL_PLANE_INTERNAL_TOKEN` must come from managed secrets and be long, non-default and rotated.
- `OPENSEARCH_URL`, `NEO4J_URI`, Kafka, Redis and PostgreSQL endpoints must use encrypted transport in production.

## Remaining external evidence

Repository tests do not replace the following production gates:

- independent penetration test against the exact release candidate and deployed ingress/realtime endpoints;
- cloud WAF, ingress, CDN and load-balancer timeout/body-size validation;
- provider-side Kafka ACL allow/deny tests for unauthorized producers and consumers;
- object-storage IAM tests proving tenants cannot list or read another tenant prefix;
- managed database/search/graph access reviews showing application identities cannot bypass tenant predicates;
- formal risk acceptance or remediation for any critical or high scanner, DAST or penetration-test finding.

Issue #29 must remain open until this evidence is attached to the issue or the release checklist.
