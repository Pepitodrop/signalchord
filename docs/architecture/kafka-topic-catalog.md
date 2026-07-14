# Kafka topic catalog

All payloads use the versioned `signalchord.v1.EventEnvelope`. Retention values are starting assumptions and must be reconciled with source rights and tenant plans. Every non-DLQ topic has a same-name `.dlq` topic with 30-day retention unless noted.

| Topic | Purpose | Producer | Consumer | Partition key | Retention / cleanup | PII | Replay and failure behavior |
|---|---|---|---|---|---|---|---|
| source.registered.v1 | Publish an enabled source configuration | Rails outbox | feed-collector | source_id | compacted, indefinite latest value | low; admin IDs | Rebuild collector registry; invalid policy to DLQ |
| source.poll.requested.v1 | Request an immediate or scheduled poll | Rails/scheduler | feed-collector | source_id | 7d delete | low | Safe to replay with poll idempotency key |
| source.document.discovered.v1 | Announce an article/feed entry | feed-collector | document-fetcher | canonical URL hash | 30d delete | possible public author names | Duplicate event produces same fetch key |
| source.document.fetched.v1 | Describe immutable raw object and HTTP response | document-fetcher | stream-normalizer | document_id | 30d delete | possible public PII | Object URI must exist; storage failure prevents publish |
| source.takedown.requested.v1 | Disable a source and remove or tombstone tenant/source derived records | Rails governance API | search-projector, recovery/runbooks | source_id | 30d delete | low; lifecycle metadata | Consumers delete or mark only matching tenant/source outputs and block reprocessing |
| document.normalized.v1 | Publish canonical normalized document metadata | stream-normalizer | search projector, audit | document_id | 90d delete | possible public PII | Rebuild projections and NLP requests |
| document.duplicate-detected.v1 | Link exact/near duplicate to canonical document | stream-normalizer | claim intelligence, metrics | canonical document_id | 90d delete | same as document | Replay uses stable duplicate edge IDs |
| document.nlp-requested.v1 | Request semantic extraction | stream-normalizer | nlp-pipeline | document_id | 30d delete | possible public PII | Model/version included in idempotency key |
| document.nlp-completed.v1 | Summarize extraction completion | nlp-pipeline | control metrics, graph workflow | document_id | 30d delete | metadata only | Replay is diagnostic; outputs remain idempotent |
| entity.mention-extracted.v1 | Emit evidence-linked mention | nlp-pipeline | entity-resolution | document_id | 90d delete | public-person data possible | Stable mention/span ID prevents duplicates |
| entity.resolution-requested.v1 | Request candidate resolution | orchestrator/NLP | entity-resolution | mention_id | 30d delete | public-person data possible | Low confidence remains unresolved |
| entity.resolved.v1 | Emit accepted/candidate resolution | entity-resolution | graph mutation builder, review queue | canonical entity or mention ID | 180d delete | public-person data possible | Replay updates candidates by model version |
| claim.extracted.v1 | Emit a source-attributed claim | nlp-pipeline | claim-intelligence | claim_id | 180d delete | sensitive/public PII possible | Never interpreted as verified platform fact |
| claim.clustered.v1 | Assign claim to semantic cluster | claim-intelligence | graph mutation builder | claim cluster ID | 180d delete | inherited | Stable cluster version; old assignments retained temporally |
| claim.contradiction-detected.v1 | Emit potential contradiction and evidence | claim-intelligence | graph mutation, review, alerts | claim cluster ID | 365d delete | sensitive | Human review can dispute/retract without deleting history |
| relationship.extracted.v1 | Emit evidence-linked relationship candidate | nlp-pipeline | graph mutation builder | subject stable/candidate ID | 180d delete | public-person data possible | Confidence/status preserved; no silent promotion |
| graph.mutation-requested.v1 | Request idempotent graph write | mutation builders | graph-projector | target stable_id | 30d delete | inherited | Parameterized `MERGE`; poison records to DLQ |
| graph.mutation-completed.v1 | Confirm an applied graph mutation | graph-projector | analytics, realtime, audit | changed stable_id | 30d delete | inherited | Stable mutation IDs make replay safe; origin/stage metadata prevents processing loops |
| graph.analytics-requested.v1 | Request bounded GDS computation | Rails/scheduler | graph-analytics | tenant/projection ID | 14d delete | tenant metadata | Expensive jobs require unique run IDs and budgets |
| intelligence.signal-created.v1 | Explain a derived graph signal | graph-analytics | policy evaluation | signal stable_id | 90d delete | inherited | Recomputed signals use versioned algorithms |
| alert.policy-evaluation-requested.v1 | Evaluate policy inputs and evidence | signal builder | velato-engine/fallback | policy version + signal ID | 30d delete | tenant/watchlist metadata | Exactly one active result per idempotency key |
| alert.created.v1 | Durable alert outcome | policy engine | realtime gateway, Rails projector | alert_id | 180d delete | tenant/user targeting | Projectors dedupe by alert_id |
| notification.requested.v1 | Request push/email/webhook delivery | alert projector | notification adapters | recipient/channel | 14d delete | contact data | External side effects use delivery idempotency ledger |
| tenant.export.requested.v1 | Record an authenticated tenant export request | Rails governance API | governance/runbooks | request_id | 30d delete | tenant metadata | Idempotency key prevents duplicate export request records |
| tenant.deletion.requested.v1 | Start tenant deletion across authoritative and derived stores | Rails governance API | governance/runbooks, replay controls | request_id | 30d delete | tenant metadata | Idempotency key prevents duplicate side effects; derived stores must tombstone or delete |
| audit.event.v1 | Append security/product audit fact | all trusted components | audit sink | tenant_id | 7y or tenant policy, delete | may contain actor identifiers | Immutable append; sensitive values redacted |

## Partition and ordering rules

- Documents: `document_id` or canonical URL hash.
- Entities: accepted stable ID; unresolved mentions remain keyed by mention ID.
- Claims: claim or claim-cluster stable ID.
- Policies: policy-version plus signal ID.
- Investigations and tenant-private objects: tenant ID plus object ID.

## Compatibility

Schemas use backward-compatible Protobuf evolution: never reuse field numbers, reserve removed fields, add optional fields with safe defaults, and test current producers against the oldest supported consumer descriptor.

## Late and out-of-order records

The envelope records source event time, ingestion time and calculated lateness. Consumers compare model/extraction version, `observed_at`, `valid_from` and stable IDs rather than assuming arrival order. Events too late for a configured online window still update the temporal graph through a reconciliation path instead of being discarded silently.
