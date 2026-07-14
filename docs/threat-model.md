# SignalChord threat model

## Assets

Tenant credentials and configuration, licensed/raw source documents, graph facts and evidence, API tokens, user identity, alert policies/MIDI files, audit history, model artifacts, source deletion state and infrastructure secrets.

## Trust boundaries

1. Internet sources to ingestion services.
2. Public clients to Rails and realtime APIs.
3. Kafka producers/consumers and Schema Registry.
4. Application services to PostgreSQL, Neo4j, object storage, Redis and OpenSearch.
5. MIDI upload to Velato parser/sandbox.
6. Human review actions to graph and audit records.
7. CI/CD to runtime clusters and registries.

## Principal threats and controls

| Threat | Controls | Verification |
|---|---|---|
| SSRF and redirect abuse | allow HTTP(S), resolve all hops, deny private/link-local/metadata ranges, source allowlists, response limits | malicious URL and DNS-rebinding tests |
| Source-rights violation | policy registry, robots/terms metadata, adapter enforcement, retention/deletion tombstones | source-policy contract tests and deletion drill |
| Cross-tenant access | tenant claims, policy authorization, injected graph predicates, tenant cache/object prefixes | negative integration tests for every resource type |
| Kafka event forgery | mTLS/SASL, ACLs, schema validation, producer identity, audit metadata | unauthorized producer tests |
| Production service starts with local credentials or plaintext endpoints | `SIGNALCHORD_ENV=production` validators reject development defaults, localhost endpoints and missing TLS/SASL/certificate settings | unit tests plus staging startup validation |
| Poison/replay storms | bounded retries, DLQ, idempotency ledger, replay approvals and rate limits | failure-recovery and replay load tests |
| Graph injection/expensive query | approved parameterized templates, depth/result/time budgets, no public Cypher | fuzzing and query-budget tests |
| Prompt/model manipulation | source text treated as data, fixed extraction APIs, model versioning, evidence validation | adversarial fixture suite |
| Defamatory conclusion | explicit source/extraction/inference labels, confidence, review gates, dispute/retraction workflows | sensitive-claim workflow tests |
| Malicious MIDI | byte/note/instruction/stack/time/memory limits, reject SysEx/unsupported instructions, isolated process without filesystem/network/shell | parser fuzzing, zip-bomb-equivalent and resource-exhaustion tests |
| Arbitrary Velato code | sealed IR and whitelist interpreter only; no dynamic eval/native calls | static IR validation and sandbox escape tests |
| Token theft | short-lived access tokens, rotating refresh tokens, secure mobile storage, revocation and device audit | authentication and mobile-storage tests |
| Supply-chain compromise | pinned dependencies, provenance/SBOM, Dependabot, secret/code/container scanning, protected branches | CI gates and periodic dependency review |
| Data exfiltration through logs | structured redaction, no raw document body or credentials, tenant-aware log access | log scanning and redaction tests |
| Destructive administrator action | least privilege, approval for deletion/replay, immutable audit records, backups | restore and privileged-action drills |

## Human review gates

Automatically generated claims involving alleged wrongdoing, identity-sensitive assertions, low-confidence entity resolution or material contradiction require human review before being labeled verified or used for high-severity external notifications.

## Residual risks

Public reporting can itself be wrong or malicious; extraction confidence is not truth probability; graph topology may amplify source concentration; third-party model and infrastructure vulnerabilities remain possible. These risks are surfaced in the UI and operational risk register rather than hidden.
