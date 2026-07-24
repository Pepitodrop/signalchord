## Backup, replay, restore and rollback verification

Branch: `feature/recovery-and-replay-hardening`
Base: `main` @ `001d6e4` (PR #94, tenant-security-hardening, merged)
Status: specification — implementation not yet started
Tracks: #26 ("Production: backup, restore, replay, rollback, and disaster recovery") — this spec is the concrete execution plan that closes it out. Related: #33 (production readiness master tracker).

This spec covers proving SignalChord can recover safely from PostgreSQL, Kafka, application, and background-job failures. Every claim below was reached by tracing actual code (scripts, consumer loops, migrations, Helm templates, CI workflows) — never inferred from file names alone. 7 architecture decisions were locked via direct confirmation before drafting (see §0).

## 0. Locked decisions (from interactive scoping, read alongside §10-§16)

1. **Deployment topology confirmed**: closed-beta production runs **single-server** (in-cluster PostgreSQL/Kafka/Neo4j/MinIO as StatefulSets in one namespace, both `signalchord` and `signalchord-community` Helm releases together). `scripts/single-server/backup.sh`/`restore-v1.sh`/`rollback.sh` are the REAL production recovery mechanism today, manually triggered. This is not a separate/parallel deployment target — everything in this spec targets hardening and automating these actual scripts, not building a parallel system.
2. **Isolated restore**: harden the real scripts (add a namespace/context safety guard to `restore-v1.sh`, add an outbound-integration-disable step) AND build a new CI-driven exercise that runs them end-to-end against a throwaway `kind` cluster, rather than only testing a parallel copy.
3. **Kafka replay tool**: a thin safety wrapper around Kafka's own built-in `kafka-consumer-groups.sh --reset-offsets`, not a custom replay engine.
4. **Poison-message handling**: one shared pattern applied to all 10 consumers (9 Python workers + the Go `kafkautil.Consume` helper used by all Go consumers), not a single-consumer pilot.
5. **Backup automation**: a new Kubernetes CronJob invoking `backup.sh` on a schedule, mirroring the existing `signalchord-feed-collector` CronJob pattern.
6. **Backup destination**: a dedicated MinIO bucket, separate from the app's own document-storage bucket. Full external-cluster-failure tolerance (replicating outside this cluster) is out of scope — flagged as a residual risk requiring ops/cloud-account work this repo can't verify (TODOS.md).
7. **Migration rollback safety**: a new CI check flagging destructive migration patterns (no such migration exists today, but nothing currently prevents one), turning the already-written `recovery-matrix.json` policy ("forward-repair only; do not reverse incompatible event contracts or destructive migrations") into an enforced check.

## 1. Complete persistence and state inventory

| Store | Where it runs | What it holds | Classification |
|---|---|---|---|
| PostgreSQL | in-cluster StatefulSet `postgres` | 18 tables: organizations, users, memberships, api_tokens, sources, watchlists+items, policies+versions, investigations, alerts, alert_email_deliveries, notification_deliveries, notification_endpoints, governance_requests, audit_events, support_tickets, invitations, usage_limits, outbox_events | **Authoritative** |
| Kafka | in-cluster StatefulSet `kafka` | ~18 topics (full list in §4) carrying event history within retention window only | **Authoritative within retention; not a permanent store** — see caveat below |
| Neo4j | in-cluster StatefulSet `neo4j` | graph nodes/relationships/evidence links | **Semi-authoritative**: rebuildable ONLY by replaying `graph.mutation-requested.v1` within Kafka's retention window (recovery-matrix.json's own `rebuild_source` says exactly this) — beyond that window, a lost Neo4j is a genuine, permanent data loss, not just an inconvenience |
| MinIO (object storage) | in-cluster StatefulSet `minio` | raw fetched document bytes, permitted-use metadata | **Authoritative** |
| OpenSearch | in-cluster StatefulSet | search index (articles, entities, claims) | **Reconstructable derived state** — confirmed: `search-projector/worker.py` rebuilds it entirely from `document.normalized.v1`/`entity.resolved.v1`/`claim.clustered.v1`/object storage, no unique data lives only here |
| Redis/Valkey | in-cluster StatefulSet | Rack::Attack throttle counters, Sidekiq queue backing, realtime subscriptions | **Ephemeral** — confirmed by direct code trace (tenant-security-hardening review): no code path treats Redis as a source of truth; losing it means rate limits reset and in-flight jobs replay, nothing unrecoverable. Per the brief's explicit constraint, this classification is proven from code, not assumed. |
| Sidekiq job payloads | Redis-backed queue | one job type (`AlertEmailNotificationJob`), holding only a DB record ID | **Ephemeral** — losing queued jobs delays a notification, never loses source data (the DB row it references is already committed) |
| Secrets/runtime config | ExternalSecret → cluster Secret | DATABASE_URL, SMTP creds, internal tokens, etc. | **Authoritative** (per recovery-matrix.json) but **external dependency** for rebuild (secret manager + Git history + provider IAM) |
| SMTP provider | external | no data stored here, delivery channel only | **External dependency** |

**Caveat on Kafka's classification**: Kafka is not a permanent authoritative store the way Postgres is — it's a durable bus with a retention window. Once a topic's retention expires, replay is impossible for anything not already reflected in Postgres/Neo4j/MinIO. This spec treats "Kafka authoritative" as shorthand for "authoritative for recovery *within* retention," matching recovery-matrix.json's own wording, and does not claim indefinite Kafka-based recovery.

## 2. Current backup architecture (verified working, not aspirational)

`scripts/single-server/backup.sh` (256 lines) is real, tested-shape tooling that:
- Requires `kubectl`/`helm`/`age`/`python3`/`sha256sum`/`tar` present, refuses to run without `--yes`, refuses if the runtime-env file isn't mode 0600.
- Quiesces the app: waits for in-flight `feed-collector` jobs to complete, suspends its CronJob, scales all `app.kubernetes.io/part-of=signalchord` deployments to 0, recording original replica counts to restore them.
- Captures Helm state (`values`, `manifest`, `history` for both `signalchord` and `signalchord-community` releases) and raw Kubernetes resource manifests.
- `pg_dump --format=custom --compress=9 --no-owner --no-acl` via `kubectl exec statefulset/postgres` (line 127-129).
- Snapshots MinIO's PVC via a throwaway backup pod running `tar` (lines 132-171) — scales MinIO to 0 first, so this is a consistent (not live/fuzzy) snapshot.
- Dumps Neo4j (`neo4j-admin database dump neo4j` + `system`) the same way (lines 174-221).
- Encrypts the runtime-env file with `age` (line 107).
- Writes a `manifest.json` recording format/version/`application_quiesced: true` and a `SHA256SUMS` checksum of every file (lines 223-246).
- Restores the app to its pre-backup replica counts before exiting, even on failure (`cleanup()` trap, lines 41-59).

`restore-v1.sh` (185 lines) verifies checksums and manifest shape (rejects a backup not created with `application_quiesced: true`), decrypts the runtime-env, then restores Postgres (`pg_restore --clean --if-exists`), MinIO (wipe + re-tar), and Neo4j (`neo4j-admin database load`) into whatever `--namespace` is passed, restarts the app, and calls `health.sh`. Kafka, OpenSearch, and Valkey are explicitly `rebuild_only` per the manifest — never backed up, always rebuilt.

`rollback.sh` (39 lines) does `helm rollback signalchord <revision>` + `health.sh` — an **application-version** rollback only, never a schema rollback.

`validate_recovery.py` + `scripts/single-server/test_release_tooling.py` are **contract/shape checkers**: they assert `recovery-matrix.json` has required fields and that the shell scripts contain expected string markers (`pg_dump`, `pg_restore`, quiesce logic). Neither executes a real backup or restore. No CI job and no CronJob currently invokes `backup.sh`/`restore-v1.sh` at all — every run today is a human at a terminal.

## 3. Current replay and idempotency architecture

**Producers**: `OutboxEvent` (Rails model, just a row) + `Outbox::Publisher#publish_batch` (`app/services/outbox/publisher.rb`) claims pending rows with `SELECT ... FOR UPDATE SKIP LOCKED`, produces with `required_acks: :all, max_retries: 5`, marks `published_at` only after `deliver_messages` succeeds, retries via `publish_attempts`/`last_error` on failure — classic poll-and-mark at-least-once, run in a loop from `bin/outbox-publisher`. Go/Python services also produce directly, with `enable.idempotence: true, acks: all` on every Python producer (confirmed in entity-resolution, graph-projector, etc.).

**Consumers**: every one of the 9 Python workers uses `confluent_kafka.Consumer` with `enable.auto.commit: False`, calling `consumer.commit(message=..., asynchronous=False)` **strictly after** the processing side effect completes (verified in all 9: alert-projector, notification-worker, entity-resolution, graph-projector, claim-intelligence, search-projector, graph-analytics, nlp-pipeline, velato-engine). The Go `kafkautil.Consume` helper (`services/internal/kafkautil/consumer.go`) does the same: `h.handle(...)` then `session.MarkMessage(...)` only on success.

**What this buys**: at-least-once delivery, never at-most-once — a crash between processing and commit means the message replays. **What it doesn't buy**: nothing currently stops a message that ALWAYS fails processing (a poison message) from blocking that partition forever, since there's no path that ever calls `commit`/`MarkMessage` for a message the handler can't process (see §6, Confirmed defect #1).

**Duplicate-delivery protection at the destination** (this is genuinely solid, verified by tracing each site):
- `Internal::V1::AlertsController#create`: `organization.alerts.find_or_initialize_by(stable_id:)`, and notification enqueue (`enqueue_notification`/`enqueue_email_notifications`) is gated on `created && !alert.suppressed?` — a replayed `alert.created.v1` for an already-persisted alert finds `created = false` and **skips re-enqueueing notifications entirely**. Confirmed by direct read of `app/controllers/internal/v1/alerts_controller.rb:10-33`.
- `notification_deliveries` unique index `idx_notification_delivery_idempotency` (migration 003).
- `alert_email_deliveries` unique index `idx_alert_email_delivery_dedup` on `(alert_id, membership_id)` (migration 009) plus `AlertEmailNotificationJob`'s own `pending→sending→delivered/failed/skipped` state machine, re-validated at execution time (from the tenant-security-hardening review — the exemplar pattern other consumers should follow).
- Neo4j writes use `MERGE` (idempotent upsert), not `CREATE`.

## 4. Current migration and rollback architecture

9 migrations exist (`apps/control-plane/db/migrate/001` through `009`), every one `class X < ActiveRecord::Migration[8.0]` with only a `def change` — **zero custom `def down` methods, zero raw SQL, zero destructive operations** (`grep` for `execute(`, `drop_table`, `drop_column`, `remove_column` across all 9 returns nothing). Reversibility today relies entirely on ActiveRecord's automatic inverse of additive operations. `rollback.sh` never touches the schema — it only rolls back the Helm release (application code/image), never runs `rails db:rollback`, and has no check that the rolled-back app version is compatible with the CURRENT (possibly newer) schema.

## 5. Confirmed recovery gaps (Blocker/High — fixed in this feature per §0)

1. **[Blocker] No backup automation.** `backup.sh` is manual-only. `recovery-matrix.json` already commits to a 15-minute Postgres RPO that manual-only backups cannot realistically hit — a real incident between manual runs could lose far more than 15 minutes.
2. **[Blocker] `restore-v1.sh` has no isolation guardrail.** `--namespace X` accepts any value, including the real production namespace, with no check preventing an operator from accidentally restoring INTO production (overwriting current data with an older backup). Directly matches the brief's "Recovery scripts modifying production accidentally" threat.
3. **[Blocker] Restored environments can send real outbound traffic.** Neither `backup.sh` nor `restore-v1.sh` disables SMTP/webhook configuration before scaling the app back up. Restoring a production-shaped backup (including pending/retry-eligible Sidekiq-adjacent state) into any environment with live SMTP credentials would let replayed processing send real customer-facing emails. Directly matches "Restored production-like data must not send real email, webhooks or notifications."
4. **[High] Zero Kafka replay tooling exists.** No script, wrapper, or documented procedure resets a consumer group's offsets in a controlled, evidenced way.
5. **[High] Zero poison-message handling across all 10 consumers.** Confirmed by reading every consume loop: none has a path that skips a permanently-failing message. A single malformed event blocks that partition indefinitely (message never gets its offset committed, handler keeps re-raising on redelivery) or crash-loops the worker.
6. **[High] No migration-rollback safeguard.** Nothing prevents a future destructive migration from silently breaking `rollback.sh`'s Helm-only rollback (old app code + a schema missing columns it expects).
7. **[High] `validate_recovery.py` proves nothing operationally.** It is a JSON-shape linter, not a functional test — no CI job has ever executed a real backup→restore cycle. `recovery-matrix.json`'s own `external_blockers` list admits the actual drills haven't happened.
8. **[High] No automated backup destination exists.** Automating backup.sh requires somewhere for scheduled runs to write to; today `--output` is always a human-supplied local path.

## 6. Confirmed replay/idempotency defects

1. **Poison-message partition blocking** (see §5.4/§5.5) — the actual defect: `handle-then-commit` with no catch-and-skip means a bad message is retried forever on every redelivery after a crash, never advancing.
2. **No evidence that duplicate Kafka replay is asserted, only architecturally plausible.** §3's dedup mechanisms are real and traced, but nothing in CI or elsewhere actually replays a message twice and asserts no duplicate customer-visible alert/email results — it's a code-review conclusion, not a proven one.
3. **Nothing prevents Sidekiq retry-after-success from double-sending**, in the sense that no test proves it — `AlertEmailNotificationJob`'s state machine (§3) should already prevent this, per the tenant-security-hardening review, but again unproven by an executable test in this repo.

No other replay defects were found — the outbox pattern, unique-constraint dedup, and `MERGE`-based graph writes are all sound as designed.

## 7. Missing automated tests

- No test executes a real `pg_dump`→`pg_restore` cycle against real data.
- No test executes a real Kafka offset-reset/replay against a real broker.
- No test asserts a duplicate alert/email doesn't result from replaying `alert.created.v1` twice.
- No test asserts a poison message is isolated without blocking a healthy message behind it (once §0.4's fix lands).
- No test asserts `restore-v1.sh` refuses to run against a namespace not explicitly marked non-production (once §0.2's guard lands).
- No test asserts outbound integrations are actually disabled post-restore (once §0.2's fix lands).
- No CI check flags a destructive migration pattern (once §0.7's linter lands).

## 8. Proposed RPO/RTO targets for closed beta

Reuse `recovery-matrix.json`'s existing numbers — they are reasonable for a closed-beta (not yet GA) product and already reviewed once (this feature's job is to make them PROVEN, not to renegotiate them):

| Store | RPO | RTO | Note |
|---|---|---|---|
| PostgreSQL | 15 min | 60 min | requires automated backup (§0.5) to be achievable at all |
| Kafka | 5 min | 60 min | replication is the in-cluster broker's own; no cross-cluster mirror in scope |
| Object storage (MinIO) | 15 min | 120 min | covered by the same backup.sh snapshot |
| Neo4j | 30 min | 180 min | rebuildable from Kafka only within retention — see §1 caveat |
| Secrets/config | 30 min | 60 min | external dependency, not solved by this feature |
| OpenSearch (derived) | 0 | 240 min | full rebuild from source events, no backup needed |
| Redis (derived) | 0 | 30 min | ephemeral, no backup needed |

## 9. Required backup automation

New Kubernetes CronJob (mirrors `feed-collector-cronjob.yaml`'s existing shape) invoking `backup.sh` on a schedule tight enough to plausibly hit the 15-minute Postgres RPO in practice (proposed: hourly full snapshot as the realistic floor for a single-server topology doing a full quiesce-scale-to-zero-and-back cycle each run — a true 15-minute cadence would mean the app is down for a meaningful fraction of every hour, which is a real tradeoff to surface, not silently accept; see §17 Phase 1 for the explicit RPO-vs-availability tradeoff this needs sign-off on). Writes to a new dedicated MinIO bucket (§0.6), separate from the app's document bucket, with a retention/rotation policy (keep N most recent, prune older).

## 10. Required isolated-restore workflow

1. Add a namespace/context safety guard to `restore-v1.sh`: refuse to run unless the target namespace carries an explicit non-production label/annotation, or a `--force-production` flag is passed with an additional typed confirmation.
2. Add an outbound-integration-disable step: before scaling the app back up post-restore, null out `SMTP_HOST` (or point it at a black-hole/mailpit-style sink) and any webhook URLs in the restored runtime-env, so replayed/retried processing can't reach real customers.
3. New CI job (`recovery-drill`, modeled on `helm-disposable-cluster` but doing real work, not a dry-run): spins up a `kind` cluster, installs the real Helm chart with real (small) images, seeds representative tenant data, runs `backup.sh`, tears down and recreates a throwaway target namespace, runs the hardened `restore-v1.sh` against it, and asserts: schema/migration state matches (`rails db:migrate:status`), tenant row counts and referential integrity hold, the app boots and answers a health check, and no outbound SMTP/webhook call was attempted (assert against a black-hole sink, not real credentials).

## 11. Required Kafka replay tooling

New `scripts/single-server/replay-kafka.sh`: wraps `kafka-consumer-groups.sh --bootstrap-server ... --group <group> --topic <topic> --reset-offsets --to-datetime <ts> --execute`, refusing to run without an explicit `--namespace` and `--group`, printing the consumer group's current offsets before and after, and refusing (without a force flag) if the target group name doesn't match one of the 9 known consumer groups (guards against fat-fingering a group name). Every invocation appends a line to the recovery evidence report (§16).

## 12. Required poison-message and dead-letter handling

One shared pattern, two implementations (matching how consumers are already structured — Python workers all hand-roll their own loop, Go consumers all route through one helper):
- **Python**: a small shared helper (new `services/python_common/poison_message.py` or similar) wrapping the handle-then-commit sequence: catch the handler's exception, track a per-message-key failure count (in-memory is acceptable for a single-partition-owning worker; document the limitation), and after N failures (proposed: 3), publish the raw message + error to a new `<topic>.dead-letter.v1` topic and commit the offset anyway (so the partition advances), instead of retrying forever.
- **Go**: the equivalent added directly to `kafkautil.Consume` (one shared function, all Go consumers already route through it), same dead-letter-topic-then-commit shape.
- Dead-letter topics need no new infrastructure — same Kafka cluster, just new topic names.

## 13. Required duplicate-delivery protections

No NEW code fix is required here beyond what's already correct (§3) — the requirement is **proof**, not new logic: the staging recovery exercise (§20) must replay `alert.created.v1` for an already-processed alert and assert exactly one alert row and zero duplicate email/push sends result, turning the current code-review-only confidence into an executable, repeatable assertion.

## 14. Required migration rollback safeguards

New CI check (script, e.g. `scripts/validate_migration_safety.py`) that inspects migration files changed in a PR diff for `drop_table`, `remove_column`, `rename_column`, `drop_column` (raw or via `change_table`), and fails the check unless the migration is explicitly annotated as reviewed-and-safe (e.g., a comment marker acknowledging the forward-repair-only policy already stated in `recovery-matrix.json`). This turns an already-written policy into an enforced one; it does not retroactively touch any of the 9 existing (all-safe) migrations.

## 15. Required observability and recovery evidence

A versioned recovery report (§20's exercise output) — not a new dashboard, a structured artifact: JSON or Markdown written per drill run, containing the fields `recovery-matrix.json`'s own `evidence_required` array already specifies (restore command log with timestamps, source/restored environment identifiers, image digests + git SHA, RPO/RTO actuals, canary result, tenant isolation validation, operator/approver) — this feature is what actually PRODUCES that evidence file for the first time; today the schema exists but nothing generates an instance of it.

## 16. Recommended phased implementation plan

1. **Phase 1 — backup automation + destination**: new MinIO bucket wiring, new CronJob invoking `backup.sh` on a schedule, explicit RPO-vs-availability tradeoff surfaced and confirmed (backup.sh's current design requires scaling the app to 0 — running it every 15 minutes means real downtime every 15 minutes; this needs an explicit call on cadence, not a silent assumption).
2. **Phase 2 — restore safety**: namespace/context guard + outbound-integration-disable in `restore-v1.sh`.
3. **Phase 3 — Kafka replay tool**: `replay-kafka.sh` wrapper.
4. **Phase 4 — poison-message handling**: shared Python helper + Go `kafkautil.Consume` extension, applied to all 10 consumers.
5. **Phase 5 — migration rollback safeguard**: new CI check.
6. **Phase 6 — the recovery-drill CI job**: the full staging exercise (§20), wiring together Phases 1-4's outputs into one real, executed proof.
7. **Phase 7 — verification**: run the new CI job to green, confirm the recovery evidence report is produced and matches `recovery-matrix.json`'s schema, update #26 and `recovery-matrix.json`'s `external_blockers` to reflect what's now actually proven vs still pending.

## 17. Files likely to change

| File | Change |
|---|---|
| `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml` | New CronJob invoking backup.sh |
| `infrastructure/kubernetes/helm/signalchord/values.yaml` | New backup schedule/bucket config |
| `scripts/single-server/restore-v1.sh` | Namespace safety guard, outbound-disable step |
| `scripts/single-server/backup.sh` | Write to new MinIO bucket destination |
| `scripts/single-server/replay-kafka.sh` | New |
| `scripts/validate_migration_safety.py` | New, + paired test |
| `services/python_common/poison_message.py` (or similar) | New shared helper |
| `services/internal/kafkautil/consumer.go` | Dead-letter extension |
| 9 Python worker `worker.py` files | Wire in the shared poison-message helper |
| `.github/workflows/ci.yml` | New `recovery-drill` job |
| `recovery/recovery-matrix.json` | Update `external_blockers` as items get proven |
| `TODOS.md` | New entries: cross-cluster backup replication, Neo4j-beyond-retention gap, per-worker in-memory failure-count limitation |

## 18. Acceptance criteria

1. A scheduled CronJob produces a real backup on a defined cadence, landing in a dedicated MinIO bucket.
2. `restore-v1.sh` refuses to run against a namespace not explicitly marked non-production, without an explicit force + confirmation.
3. A restored environment does not attempt any real outbound SMTP/webhook call (asserted against a black-hole sink in the CI drill).
4. `replay-kafka.sh` resets a named consumer group's offsets to a controlled point and logs the before/after state.
5. All 10 Kafka consumers isolate a poison message to a dead-letter topic after N failures instead of blocking the partition indefinitely.
6. Replaying `alert.created.v1` for an already-processed alert produces exactly one alert row and zero duplicate email/push sends (asserted by an executable test).
7. A CI check fails a PR that introduces a destructive migration pattern without explicit acknowledgment.
8. The `recovery-drill` CI job runs backup → restore → schema/migration verification → tenant row-count/referential-integrity check → Kafka replay → poison-message isolation → derived-state rebuild → app boot, end to end, and produces a versioned recovery evidence report matching `recovery-matrix.json`'s `evidence_required` schema.
9. No existing test regresses.
10. `recovery-matrix.json`'s `external_blockers` list is updated to remove items this feature actually proves.

## 19. Files reference

See §17.

## 20. Exact staging recovery exercise

New CI job `recovery-drill` (`.github/workflows/ci.yml`), triggered on PRs touching `scripts/single-server/`, `recovery/`, or Helm backup/restore templates (plus manually via `workflow_dispatch`):

1. Spin up a `kind` cluster (same action as `helm-disposable-cluster`, but installing the REAL chart with real small images, not a dry-run template).
2. Install `signalchord` + `signalchord-community` releases into a `signalchord` namespace.
3. Seed representative multi-tenant data (reuse `db/seeds.rb`'s pattern, extended to 2+ tenants).
4. Run `backup.sh --output <path> --runtime-env <fixture> --age-recipient <test-key> --yes`. Assert exit 0 and manifest/checksum files exist.
5. Create a throwaway `signalchord-restore-drill` namespace with the same chart installed (fresh, empty state), explicitly labeled non-production.
6. Run the hardened `restore-v1.sh --namespace signalchord-restore-drill ...`. Assert it refuses if the namespace label is missing (negative test), then succeeds against the correctly-labeled namespace.
7. Assert schema/migration state: `rails db:migrate:status` shows nothing pending.
8. Assert tenant row counts and referential integrity: row counts per tenant match the pre-backup seed, no orphaned foreign keys.
9. Assert no outbound call: SMTP/webhook config points at a black-hole sink; assert zero connections were attempted.
10. Run `replay-kafka.sh` against a test topic/group with 3 messages, one intentionally malformed. Assert the 2 healthy messages are processed and the malformed one lands on its dead-letter topic, not blocking the others.
11. Assert derived-state rebuild: trigger the search-projector's rebuild path, assert OpenSearch document counts match the restored authoritative records.
12. Assert the app boots and answers a health check in the restored namespace.
13. Write the versioned recovery evidence report (§16) as a CI artifact.

## 21. Recommended next gstack command

`/plan-eng-review` — this spec introduces a new CI job with real infrastructure (kind cluster, seeded multi-tenant data, a full backup/restore/replay cycle), modifies production-critical shell scripts operators actually run today, and touches 10 separate Kafka consumers across 2 languages — exactly the kind of cross-cutting, infrastructure-heavy change that benefits from a dedicated engineering review pass before implementation starts, matching the pattern used for all 4 prior features in this session.

## 22. Eng-review corrections and decisions (locks §5/§6/§9/§12/§16/§17/§20, read alongside them)

The following were found and decided during `/plan-eng-review` (2026-07-24) and take precedence over the corresponding prose above:

- **Poison-message handling is NOT "zero across all 10 consumers" (correction to §5.5/§6.1).** `services/graph-projector/worker.py` already has a real, working pattern: `class PermanentMutationError(ValueError)` raised on unprocessable events, caught, published to `DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"`, offset committed; any OTHER exception is left uncaught (crashes the pod, correctly letting Kubernetes restart it for transient errors — a deliberate, sound distinction, not a gap). Further, `.dlq` topics for **every** topic are already auto-provisioned by `signalchord-community`'s `templates/init-jobs.yaml` (Helm post-install/upgrade hook) and its docker-compose twin `scripts/create-topics.sh` — a completely separate Helm chart (`infrastructure/kubernetes/helm/signalchord-community/`) my initial research pass missed entirely. **§12's shared pattern is now: extract graph-projector's proven `PermanentMutationError`-vs-uncaught-exception distinction into `services/python_common/`, apply to the other 8 Python workers; design the Go `kafkautil.Consume` equivalent with the same two-tier (permanent → DLQ-and-commit, transient → propagate-and-crash-loop) shape. Use the existing `.dlq` naming — no new Kafka topics, no new provisioning.**
- **Restore-safety guard signal (correction to §10/§16 Phase 2).** `values-single-server.yaml` — confirmed via `scripts/single-server/install.sh:79` as the file the real production install actually uses — sets `global.environment: staging`, which becomes `SIGNALCHORD_ENV=staging` on every pod (`deployments.yaml:60`, `feed-collector-cronjob.yaml:36`, `migration-job.yaml:36`). Real production is mislabeled staging today. This is a genuine, separate bug (flagged in TODOS.md, not fixed here — fixing it risks flipping on FORCE_SSL/TLS/secret-strength requirements the running deployment may not satisfy, real production blast radius outside this feature's scope). For this feature: **`restore-v1.sh`'s safety guard does NOT use `SIGNALCHORD_ENV`/`environment` at all.** It requires an explicit new namespace annotation (e.g. `signalchord.io/restore-target: allowed`) that only a legitimately-intended restore target ever carries — fail-closed by default (an unlabeled namespace, including real production under any current or future label, is refused), not a block-list trying to detect and exclude production.
- **[EUREKA] Two-cadence backup, not one (correction to §9/§16 Phase 1).** `backup.sh`'s full quiesce-everything design is only strictly necessary for MinIO (a live PVC tar would be inconsistent) and Neo4j (its dump tool requires the DB stopped) — **not** for PostgreSQL, since `pg_dump` takes an MVCC-consistent snapshot as of its start time even against a live, concurrently-written database. The CronJob (§9) is now **two schedules**: a new lightweight Postgres-only script on a tight cadence (proposed: every 15 min, matching the RPO, with zero app quiescing) plus the existing full `backup.sh` on a much longer cadence (proposed: daily) matching MinIO/Neo4j's looser 120/180-min RTOs. This actually hits the stated RPO instead of forcing a choice between frequent downtime and an unstated data-loss window.
- **New test additions:** `services/python_common/test_poison_message.py`, matching the 100%-consistent existing convention in that directory (`production_config.py` → `test_production_config.py`). The §20 CI exercise gets one more assertion: run the lightweight Postgres-only backup path and confirm app deployments were never scaled down during it — proving the "no downtime" claim rather than assuming it from reading the script.
- **New `scripts/validate_migration_safety.py`** should follow the exact existing `validate_recovery.py` shape (argparse, a `validate_X` function returning a failures list, printed to stderr, paired `test_validate_migration_safety.py`) — confirmed as a genuinely new capability, not overlapping with `scripts/audit_repository_history.py` (a secrets/publication-blocker scanner, unrelated purpose).

New TODOS.md entry (not fixed here): `SIGNALCHORD_ENV=staging` mislabeling of the real single-server production deployment silently disables `ProductionConfig.production_environment?`-gated hardening (cookie Secure flag from tenant-security-hardening, plus the pre-existing boot-time TLS/secret-strength validation in `ProductionConfig.validate!`) — needs its own dedicated spec given the blast radius of flipping those checks on for a currently-running deployment.

## 23. Outside-voice corrections (cross-model review, locks §16/§17/§20 further)

A Claude subagent outside-voice pass (Codex unavailable — 401, consistent all session) traced actual code beyond this review's own pass and found 3 more real gaps:

- **Backup/restore path mismatch (correction to §22's two-cadence design).** `restore-v1.sh:63-76` hard-rejects any backup manifest missing `minio.tar`/`neo4j.dump`/`neo4j-system.dump` — the lightweight Postgres-only backup could never be restored through it as drafted, and full disaster recovery still needs the full (daily) backup as its baseline regardless of cadence. **Fix: a new `--postgres-only` restore path (accepting a manifest with just `{postgresql, runtime-config}`) for the Postgres-only-corruption case, plus an explicit documented-and-exercised reconciliation step for full DR — replay Kafka (within its 30-day retention, confirmed in `init-jobs.yaml`) to bring a restored-from-full-backup Neo4j/MinIO forward to match a more-recent Postgres state.**
- **Cluster-context blind spot (addition to §10/§16 Phase 2).** Neither script ever prints or checks `kubectl config current-context` — an operator whose kubeconfig silently points at production gets zero warning before the script starts acting. **Fix: both `backup.sh` and `restore-v1.sh` print the current context prominently and require the operator to retype it as an explicit confirmation, on top of (not instead of) the namespace annotation guard.** A cluster-level admission-webhook/OPA policy would be the fully airtight version but is new infrastructure outside this feature's scope — tracked in TODOS.md as a residual risk, not fixed here.
- **Poison-message "extraction" is 8 judgment calls, not a find-replace (correction to §22's poison-message item).** Confirmed by direct trace: `alert-projector`, `entity-resolution`, `claim-intelligence`, `graph-analytics` raise no permanent/transient distinction today (bare `RuntimeError`); `search-projector`/`nlp-pipeline` raise plain `ValueError` with no distinguishable subclass; `notification-worker` conflates a permanent hard-bounce and a transient rate-limit under the same exception type. **Phase 4 is now: build the shared `services/python_common/` classification + DLQ-publish-then-commit helper, then for EACH of the 8 workers, do real analysis of which of ITS OWN exceptions are genuinely permanent vs transient** — this is real per-worker design work, not mechanical. On Go: `kafkautil.Consume` (`consumer.go:15-30`) has no producer parameter at all, and `realtime-gateway` has zero existing Kafka-producer code — DLQ support there means extending `Consume`'s signature to accept an optional producer + DLQ topic AND wiring a brand-new producer into `realtime-gateway` specifically for this, not just reusing shared code (`stream-normalizer`/`document-fetcher` already hold a producer and are more mechanical).

The outside voice's overall scope verdict was to split this into 5 separate PRs. Per Step 0's already-locked decision (proceed as scoped across all 7 phases, since every piece is an independently-justified Blocker/High fix) — **not adopted, phases stay as one feature/branch**, but the 3 corrections above are folded into the phase designs so each phase is now actually correct, not just directionally right.

## NOT in scope

| Item | Rationale |
|---|---|
| Cross-cluster backup replication (surviving total cluster/PVC loss, not just app/Postgres failure) | Requires real external cloud infrastructure and credentials this repo can't provision or verify — TODOS.md |
| Fixing the `SIGNALCHORD_ENV=staging` mislabeling on the real production deployment | Real, separate bug, but flipping FORCE_SSL/TLS/secret-strength enforcement on for a currently-running deployment has its own production blast radius deserving a dedicated spec — TODOS.md |
| A cluster-level admission-webhook/OPA policy enforcing the restore-target annotation | The script-level check + context-confirmation is the pragmatic floor; an unbypassable cluster-enforced policy is new infrastructure outside this feature — TODOS.md |
| Notification-worker's provider-level error taxonomy (hard-bounce vs rate-limit) beyond what's needed for its own poison-message classification | Real gap, but a full provider-error-taxonomy overhaul is bigger than "extend poison-message handling" — do the minimum classification needed for THIS feature, document the rest |
| Full external-managed-Postgres backup/restore path | Confirmed out of scope — real production runs single-server (in-cluster Postgres), not the managed/external topology |

## What already exists (reused, not rebuilt)

- **`scripts/single-server/backup.sh`/`restore-v1.sh`/`rollback.sh`** — the real, working backup/restore/rollback mechanism, hardened in place rather than replaced.
- **`.dlq` Kafka topics** — already auto-provisioned for every topic by `signalchord-community`'s `init-jobs.yaml` and `scripts/create-topics.sh`. Zero new topic provisioning needed.
- **`graph-projector`'s `PermanentMutationError` pattern** — the proven reference implementation the shared poison-message helper is extracted from, not invented fresh.
- **`validate_recovery.py`'s argparse/failures-list shape** — the exact convention the new `validate_migration_safety.py` follows.
- **`services/python_common/`'s paired-test convention** (`production_config.py` → `test_production_config.py`) — followed for the new `poison_message.py`.
- **Kafka's own `kafka-consumer-groups.sh --reset-offsets`** — the replay mechanism reused, not reimplemented.
- **`recovery-matrix.json`'s existing RPO/RTO targets and evidence schema** — reused as-is (§8), not renegotiated.
- **The `helm-disposable-cluster` CI job's `kind`-cluster pattern** — the model for the new `recovery-drill` job, though the new job does real work (not a dry-run template).

## Diagrams recommended for implementation

**1. Two-cadence backup + restore flow (inline comment in the new backup CronJob template and restore scripts):**
```
EVERY 15 MIN                          EVERY 24H (or configured cadence)
[Postgres-only backup]                [Full quiesce backup: backup.sh]
  pg_dump (no quiesce, MVCC-safe)       scale app to 0
  -> MinIO bucket                       pg_dump + minio tar + neo4j dump
  manifest: {postgresql, runtime}       -> MinIO bucket
                                        manifest: {postgresql, minio, neo4j,
                                                    neo4j-system, runtime}
        |                                        |
        v                                        v
[restore --postgres-only]              [restore-v1.sh, full]
  Postgres-corruption-only case          Full DR baseline
        |                                        |
        +------------------> [replay-kafka.sh reconciliation] <---+
                          (bring restored state forward to the
                           most recent point within 30-day retention)
```

**2. Poison-message classification (inline comment in `services/python_common/poison_message.py`):**
```
message arrives -> handler(message)
                       |
              +--------+--------+
              |                 |
       permanent error    transient error
       (bad input, will    (network blip,
        never succeed)      should retry)
              |                 |
      publish to .dlq      re-raise uncaught
      commit offset        (crash-loop; pod
      (partition           restarts, message
       advances)           redelivers)
```

## Failure modes (new codepaths from this review's corrections)

| Codepath | Realistic failure | Test? | Error handling? | User-visible? |
|---|---|---|---|---|
| Postgres-only backup (D3) | pg_dump fails mid-run (disk full on MinIO bucket) | Yes (§20 assertion) | Script exits non-zero, no partial file left uncommitted | Loud (CronJob failure alert) |
| `restore-v1.sh --postgres-only` | Backup manifest doesn't match expected shape | Yes (mirrors existing manifest-shape check) | Rejects with clear error, matching existing `restore-v1.sh:66-77` pattern | Loud |
| Namespace annotation guard | Operator forgets to annotate a legitimate new staging namespace | Not directly tested (documented operator step) | Fails closed (refuses), not silent | Loud — script exits with a clear message |
| Cluster-context confirmation | Operator retypes the wrong context by mistake, defeating the check | No — this is a human-attention control, not a code path | N/A — inherent limit of a confirmation prompt | Depends entirely on operator attention, flagged as a residual risk |
| Per-worker poison-message classification | A worker misclassifies a transient error as permanent, sending a retryable message to `.dlq` prematurely | Yes, per-worker unit test asserting the classification | DLQ message retains full original payload + error, so it's not lost, just requires manual replay | Silent unless someone checks the `.dlq` topic — flagged as needing the observability in §16 |

No critical gaps (no codepath has zero test AND zero error handling AND silent failure).

## Worktree parallelization strategy

| Lane | Modules touched | Depends on |
|---|---|---|
| A — Backup automation | `scripts/single-server/backup-postgres-only.sh` (new), `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml`, `values.yaml` | — |
| B — Restore safety | `scripts/single-server/restore-v1.sh`, new `restore-postgres-only.sh`, cluster-context confirmation in both | — |
| C — Kafka replay | `scripts/single-server/replay-kafka.sh` (new) | — |
| D — Poison-message (Python) | `services/python_common/poison_message.py` (new) + 8 worker files | — |
| E — Poison-message (Go) | `services/internal/kafkautil/consumer.go`, `services/realtime-gateway/main.go` (new producer wiring) | — |
| F — Migration safety | `scripts/validate_migration_safety.py` (new) | — |
| G — Recovery-drill CI job | `.github/workflows/ci.yml` | Lanes A, B, C, D, E (exercises all of them together) |

**Execution order:** Launch A, B, C, D, E, F in parallel (6 independent worktrees — zero shared modules, each is a genuinely separate concern). Merge all six. Then G (depends on every other lane actually existing to have something to exercise).

**Conflict flags:** None — no two parallel lanes touch the same module directory.

## Implementation Tasks

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — backup — New Postgres-only backup script (no app quiescing) + CronJob
  - Surfaced by: [EUREKA] two-cadence design (§22)
  - Files: `scripts/single-server/backup-postgres-only.sh`, `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml`, `values.yaml`
- [ ] **T2 (P1, human: ~1.5h / CC: ~15min)** — backup — Full-backup CronJob on a longer cadence, dedicated MinIO bucket destination
  - Surfaced by: §9/§0.6
  - Files: same templates as T1, plus new MinIO bucket wiring
- [ ] **T3 (P1, human: ~2h / CC: ~20min)** — restore — New `--postgres-only` restore path + manifest handling
  - Surfaced by: outside-voice correction (§23)
  - Files: `scripts/single-server/restore-v1.sh` or a new sibling script
- [ ] **T4 (P1, human: ~1h / CC: ~10min)** — restore — Namespace annotation guard + cluster-context confirmation
  - Surfaced by: §22 + §23 outside-voice addition
  - Files: `scripts/single-server/backup.sh`, `restore-v1.sh`
- [ ] **T5 (P1, human: ~1h / CC: ~10min)** — restore — Outbound-integration-disable step
  - Surfaced by: §5.3 Blocker
  - Files: `scripts/single-server/restore-v1.sh`
- [ ] **T6 (P2, human: ~2h / CC: ~20min)** — kafka — Replay wrapper script
  - Surfaced by: §11
  - Files: `scripts/single-server/replay-kafka.sh`
- [ ] **T7 (P1, human: ~3h / CC: ~30min)** — poison-message — Shared Python classification + DLQ helper
  - Surfaced by: §12, corrected by §23
  - Files: `services/python_common/poison_message.py`, `test_poison_message.py`
- [ ] **T8 (P1, human: ~4h / CC: ~40min)** — poison-message — Per-worker classification, 8 Python workers
  - Surfaced by: §23 outside-voice correction — real per-worker judgment calls, not mechanical
  - Files: 8 `worker.py` files (alert-projector, notification-worker, entity-resolution, claim-intelligence, search-projector, graph-analytics, nlp-pipeline, velato-engine)
- [ ] **T9 (P1, human: ~2h / CC: ~20min)** — poison-message — Go `kafkautil.Consume` extension + `realtime-gateway` producer wiring
  - Surfaced by: §23 outside-voice correction
  - Files: `services/internal/kafkautil/consumer.go`, `services/realtime-gateway/main.go`
- [ ] **T10 (P2, human: ~1h / CC: ~10min)** — migrations — Destructive-pattern CI linter
  - Surfaced by: §14
  - Files: `scripts/validate_migration_safety.py`, paired test
- [ ] **T11 (P1, human: ~4h / CC: ~40min)** — CI — `recovery-drill` job (full staging exercise)
  - Surfaced by: §20, depends on T1-T9
  - Files: `.github/workflows/ci.yml`

## Completion summary

- Step 0: Scope Challenge — **scope accepted as-is** (5 genuinely independent Blocker/High mechanisms, not padding)
- Architecture Review: **3 issues found** (poison-message factual error, restore-safety signal, two-cadence eureka) — all resolved
- Code Quality Review: **1 issue found** (validate_migration_safety.py convention alignment) — resolved, no user decision needed
- Test Review: **2 gaps identified** (poison_message.py missing test, two-cadence CI coverage) — both resolved
- Performance Review: **0 blocking issues** (recovery-drill CI scoping already sensible; pg_dump compression cost noted as an implementation detail, not a decision)
- NOT in scope: written
- What already exists: written
- TODOS.md updates: **1 item** (SIGNALCHORD_ENV mislabeling) — pending presentation below
- Failure modes: **0 critical gaps flagged**
- Outside voice: ran (Claude subagent — Codex 401 as all session) — **3 additional real gaps found and resolved**
- Parallelization: 7 lanes, 6 parallel / 1 sequential (recovery-drill depends on the rest)
- Lake Score: 9/9 recommendations chose the complete option

## 24. Final Implementation Plan

This section is the single source of truth for implementation — it supersedes §9/§16/§17/§20's original prose wherever they conflict (those sections remain as the research trail; this one is what to build). Written 2026-07-24, following a second review pass against 17 specific structural requirements plus 2 more design refinements (per-worker poison-message rule, PR packaging).

### 24.1 Blocker/High (fixed in this feature) vs Medium/Low (documented only)

**Blocker/High — fixed here:**

| # | Finding | Severity |
|---|---|---|
| 1 | No backup automation (manual-only, can't hit 15-min RPO) | Blocker |
| 2 | `restore-v1.sh` has no isolation guardrail (can target any namespace, including prod) | Blocker |
| 3 | Restored environments can send real outbound traffic (SMTP, Expo push — no disable step) | Blocker |
| 4 | Zero Kafka replay tooling | High |
| 5 | Poison messages block a partition indefinitely (9 of 10 consumers) | High |
| 6 | No migration-rollback safeguard against a future destructive migration | High |
| 7 | `validate_recovery.py` proves nothing operationally (shape-check only) | High |
| 8 | No backup/restore path exists for a lightweight, no-downtime cadence | High (found during this review) |
| 9 | Backup/restore has no cluster-context confirmation (wrong-cluster risk) | High (found during outside-voice pass) |

**Medium/Low — documented in TODOS.md, not fixed here** (each would materially expand scope beyond backup/replay/restore):
- `SIGNALCHORD_ENV=staging` mislabeling of real production (§0 requirement #2 — explicitly does NOT block this feature's recovery work, since the restore-safety guard was deliberately designed to not depend on this label at all; fixing the mislabeling itself has independent production blast radius — own dedicated spec).
- Cross-cluster backup replication (surviving total cluster/PVC loss).
- Cluster-level admission-webhook/OPA policy enforcing the restore-target annotation (script-level check + context confirmation is the pragmatic floor for this feature).
- Full Expo/notification-provider error-code taxonomy beyond the one targeted `DeviceNotRegistered` fix.
- Remaining 4 unrescued `RecordNotUnique` idempotency sites (pre-existing, from `tenant-security-hardening`, unrelated to this feature).
- Neo4j's "beyond Kafka retention = permanent loss" characteristic — documented as a residual risk, not solvable without either infinite Kafka retention (impractical) or a dedicated Neo4j backup cadence tighter than the 30-day event log (real infra cost/tradeoff for a future spec if it matters more than currently assessed).

### 24.2 Authoritative vs reconstructable stores (see §1 for full detail)

**Authoritative** (real, permanent data — lost forever if not backed up): PostgreSQL, MinIO (object storage), secrets/config (external dependency for rebuild).
**Semi-authoritative** (real but only recoverable within a window): Kafka (durable bus, not permanent — recovery only within retention), Neo4j (rebuildable ONLY by replaying `graph.mutation-requested.v1` within that same retention window).
**Reconstructable derived state** (zero backup needed, full rebuild from source events): OpenSearch.
**Ephemeral** (proven by code trace, not assumed): Redis/Valkey, Sidekiq job payloads.

### 24.3 Exact backup and restore path — PostgreSQL, MinIO, Neo4j

**Two cadences, not one** (PostgreSQL backup does NOT require downtime — `pg_dump` takes an MVCC-consistent snapshot of a live, concurrently-written database; only MinIO and Neo4j need the app stopped, since neither has a live-consistent snapshot mechanism as currently configured):

```
EVERY 15 MIN (tight, matches Postgres RPO)     EVERY 24H (matches MinIO/Neo4j's looser RTO)
[backup-postgres-only.sh]                       [backup.sh — existing, unchanged shape]
  pg_dump (NO app quiescing, MVCC-safe)           scale app to 0 (quiesce)
  -> dedicated MinIO bucket                       pg_dump + minio tar + neo4j dump + neo4j-system dump
  manifest: {postgresql, runtime-config}          -> same dedicated MinIO bucket
                                                   manifest: {postgresql, minio, neo4j, neo4j-system, runtime-config}
        |                                                   |
        v                                                   v
[restore-v1.sh --postgres-only]                 [restore-v1.sh, full — existing path]
  Postgres-corruption-only case                    Full disaster-recovery baseline
        |                                                   |
        +--------------------> [replay-kafka.sh reconciliation, within 30-day retention] <---+
                    (bring a restored-from-full-backup Neo4j/MinIO forward to match
                     a more-recent Postgres state, when the two cadences have drifted)
```

Both restore paths add, before scaling the app back up: (a) an explicit namespace-annotation check (`signalchord.io/restore-target: allowed` — fails closed if absent, does NOT use `SIGNALCHORD_ENV`/`environment`, which is confirmed mislabeled on real production), (b) a printed `kubectl config current-context` with a required retype-to-confirm step, (c) an outbound-integration-disable step (below).

### 24.4 Outbound-safety controls (traced, not assumed)

Three real outbound channels exist, all traced to actual code — not just "SMTP + generic webhooks" as originally drafted:
1. **SMTP** (`ApplicationMailer`, `AlertEmailNotificationJob`) — real customer emails.
2. **Expo push notification API** (`notification-worker/worker.py:16`, `EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"`) — a real third-party service, notifies real devices. Confirmed as the actual delivery path for `ios`/`android`/`expo` platform notification endpoints.
3. **Webhook platform**: registrable (`NotificationEndpoint::PLATFORMS` includes `"webhook"`) but **not actually implemented** — `notification-worker/worker.py:58-59` explicitly rejects any platform other than `expo`/`ios`/`android` with `raise ValueError(...)`. No customer webhook receives outbound traffic today even if registered. (This also means the "webhook" case is already a naturally-permanent poison-message case for this worker under §24.5's rule — no new code needed to classify it.)

Restore-time fix: null/redirect `SMTP_HOST` to a black-hole sink and set `EXPO_PUSH_URL` to a local black-hole endpoint (e.g., a stub HTTP server in the CI drill returning 200 with no real delivery) in the restored runtime-env, before scaling the app back up.

### 24.5 Kafka replay boundaries, offset handling, duplicate-suppression

- **Boundary**: replay is only possible within each topic's retention window (30 days for standard topics, confirmed in `signalchord-community/templates/init-jobs.yaml`; `source.registered.v1` is compacted/infinite). Beyond that window, replay is impossible — not a tooling gap, a hard boundary of the architecture (§1 caveat).
- **Tool**: `scripts/single-server/replay-kafka.sh`, a thin wrapper around `kafka-consumer-groups.sh --reset-offsets --to-datetime <ts> --execute`, refusing to run without explicit `--namespace`/`--group`, validating the group name against the 9 known consumer groups, printing before/after offsets, and appending to the recovery evidence report.
- **Duplicate-suppression guarantee, traced end to end** (§3): a replayed `alert.created.v1` for an already-persisted alert hits `find_or_initialize_by(stable_id:)` in `Internal::V1::AlertsController#create`, finds `created = false`, and skips the entire notification-enqueue block (`enqueue_notification`/`enqueue_email_notifications`) — **zero duplicate customer-visible side effects from alert replay specifically**, by construction. This is the ONE customer-visible side-effect path traced from Kafka ingestion through to email/push. No other Kafka-triggered customer-visible side effect exists in this codebase (verified: no other consumer sends email, push, or webhook traffic — only the alert → notification-worker → Expo path does).
- **Requirement is proof, not new code** (§13): the recovery-drill CI job replays `alert.created.v1` for an already-processed alert and asserts exactly one alert row + zero duplicate Expo push calls (against a stub Expo endpoint) + zero duplicate email sends (against mailpit/black-hole).

### 24.6 Poison-message behavior — every consumer in scope, individually evaluated

Reference implementation (already correct, preserved as-is): `graph-projector/worker.py:52,252,259,262` — `PermanentMutationError(ValueError)` raised on unprocessable events, published to `DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"`, offset committed; anything else uncaught (crash-loop, correct for transient errors).

**Generalized rule** (mechanical, not 8 separate judgment calls — locked via direct code trace of every worker's actual raise/except sites):

> **`ValueError` and subclasses → permanent (publish to `.dlq`, commit offset). Everything else → transient (propagate uncaught, crash-loop, Kubernetes restarts the pod).**

| Consumer | Current error handling (traced) | Change needed |
|---|---|---|
| `graph-projector` | `PermanentMutationError(ValueError)` for bad mutations; else uncaught | **None** — already correct, this IS the reference pattern |
| `search-projector` | `ValueError("document exceeds search projection limit")` (line 89); else uncaught | Wire into shared helper — already raises the right type |
| `nlp-pipeline` | 3x `ValueError` for oversized/missing input (lines 74/78/87); else uncaught | Wire into shared helper — already raises the right type |
| `notification-worker` | `ValueError` for unsupported platform (line 59, already correct — webhook case); `RuntimeError(provider_error)` for Expo API errors (line 66, **ambiguous** — conflates permanent token failures and transient rate-limits) | Wire into shared helper; **targeted fix**: recognize Expo's `DeviceNotRegistered` error and raise `ValueError` for it specifically — everything else stays `RuntimeError` (transient), which is the safe default for an unrecognized provider error |
| `alert-projector` | Only generic Kafka-transport `RuntimeError(message.error())`; no payload validation exists | Wire into shared helper (no new validation needed — no permanent-error case exists in this worker today, and none is being invented; it correctly has nothing to classify as permanent yet) |
| `entity-resolution` | Same as alert-projector | Same — wire into shared helper, no new validation |
| `claim-intelligence` | Same as alert-projector | Same |
| `graph-analytics` | Same as alert-projector | Same |
| `velato-engine` | Same Kafka-transport pattern in its consume loop; a separate try/except at startup (policy-file loading) is unrelated to message processing | Same — wire into shared helper, no new validation |
| Go (`kafkautil.Consume`, all Go consumers) | Any handler error is fatal to the whole claim; no producer parameter exists at all | Extend `Consume`'s signature to accept an optional `(producer, dlqTopic)` pair; classify via a Go error type (e.g. a `PermanentError` wrapper the handler can return) with the same two-tier shape; wire a **new** Kafka producer into `realtime-gateway` specifically (it has none today) |

This is intentionally NOT "add new validation to 4 workers" — it's "give the 4 workers with nothing to classify yet a helper that's ready the moment they do," while the 4 workers that already raise the right exception type just need to route through it.

### 24.7 Migration rollback and forward-fix strategy

- **Current state**: all 9 migrations are additive-only (verified, zero destructive operations exist). `rollback.sh` only rolls back the Helm app-version, never the schema.
- **Forward-fix policy** (already written in `recovery-matrix.json`, now enforced): "forward-repair only; do not reverse incompatible event contracts or destructive migrations." A destructive migration is fixed by writing a NEW additive migration that repairs forward, not by rolling the schema back.
- **New enforcement**: `scripts/validate_migration_safety.py` (matching `validate_recovery.py`'s exact argparse/failures-list shape) scans migration files changed in a PR diff for `drop_table`/`remove_column`/`rename_column`/`drop_column`, fails the CI check unless explicitly acknowledged with a comment marker citing the forward-repair policy.

### 24.8 CI tests, integration tests, recovery evidence artifacts

- **CI job `recovery-drill`** (`.github/workflows/ci.yml`, triggered on PRs touching `scripts/single-server/`, `recovery/`, Helm backup/restore templates, plus `workflow_dispatch`): see §24.9 for exact steps.
- **Unit/integration tests** (per phase, see §24.10).
- **Recovery evidence artifact**: a versioned JSON/Markdown report per drill run, containing exactly the fields `recovery-matrix.json`'s own `evidence_required` array specifies (restore command log with timestamps, source/restored environment identifiers, image digests + git SHA, RPO/RTO actuals, canary result, tenant isolation validation, operator/approver) — this feature is what first produces a real instance of that schema.

### 24.9 Isolated staging restore exercise — executable steps

1. Spin up a `kind` cluster (same GitHub Action as `helm-disposable-cluster`, but installing the real chart with real small images — actual work, not a dry-run template).
2. Install `signalchord` + `signalchord-community` releases into a `signalchord` namespace, annotated as a non-production restore target.
3. Seed representative multi-tenant data (extends `db/seeds.rb`'s pattern to 2+ tenants).
4. Run the lightweight `backup-postgres-only.sh`. Assert: exit 0, manifest present, **app deployments were never scaled down during the run** (proves the no-downtime claim).
5. Run the full `backup.sh`. Assert exit 0, manifest/checksum files present.
6. Create a throwaway `signalchord-restore-drill` namespace, same chart installed fresh/empty, explicitly annotated as an allowed restore target.
7. Print `kubectl config current-context` and confirm the drill's automated confirmation matches (proves the confirmation step is wired, not bypassed).
8. Run `restore-v1.sh --namespace signalchord-restore-drill` (negative test first: assert it refuses against an unannotated namespace; positive test: succeeds against the correctly-annotated one). Point `SMTP_HOST`/`EXPO_PUSH_URL` at black-hole stubs before scaling the app up.
9. Assert schema/migration state: `rails db:migrate:status` shows nothing pending.
10. Assert tenant row counts and referential integrity match the pre-backup seed.
11. Assert zero real outbound calls: the SMTP/Expo stub endpoints recorded zero connection attempts.
12. Run `replay-kafka.sh` against a test topic/group with 3 messages, one intentionally malformed (a payload triggering a `ValueError`-classified failure). Assert: the 2 healthy messages process normally, the malformed one lands on `.dlq` without blocking the others.
13. Replay `alert.created.v1` for an already-processed alert. Assert exactly one alert row and zero duplicate Expo-push/email calls result (§24.5's guarantee, now proven not just traced).
14. Assert derived-state rebuild: trigger `search-projector`'s consume path, assert OpenSearch document counts match the restored authoritative records.
15. Assert the app boots and answers a health check in the restored namespace.
16. Also restore via the **`--postgres-only` path** separately (Postgres-corruption-only scenario), asserting it succeeds against a manifest containing only `{postgresql, runtime-config}`.
17. Write the versioned recovery evidence report as a CI artifact.

### 24.10 Implementation phases — files, tests, and PR packaging

**PR1 — Backup automation + restore safety** (Blockers #1/#2/#3/#8/#9):
- Files: `scripts/single-server/backup-postgres-only.sh` (new), `scripts/single-server/backup.sh` (MinIO bucket destination), `scripts/single-server/restore-v1.sh` (`--postgres-only` path, namespace annotation guard, cluster-context confirmation, outbound-disable for SMTP + Expo), `infrastructure/kubernetes/helm/signalchord/templates/backup-cronjob.yaml` (new, two schedules), `values.yaml`.
- Tests: shell-script assertions in the (not-yet-existing) `recovery-drill` job are deferred to PR5, but each script gets its own quick unit-style check where feasible (e.g., `test_release_tooling.py`-style contract tests extended to check for the new manifest shape and annotation-guard logic strings).

**PR2 — Kafka replay + migration safety** (High #4/#6):
- Files: `scripts/single-server/replay-kafka.sh` (new), `scripts/validate_migration_safety.py` (new) + paired test.
- Tests: `test_validate_migration_safety.py` (matching `validate_recovery.py`'s existing test convention).

**PR3 — Poison-message, Python** (High #5):
- Files: `services/python_common/poison_message.py` (new, the `ValueError`-classification helper) + `test_poison_message.py`; wire into `graph-projector` (no behavior change, just routes through the shared helper), `search-projector`, `nlp-pipeline`, `notification-worker` (+ the targeted `DeviceNotRegistered` fix), `alert-projector`, `entity-resolution`, `claim-intelligence`, `graph-analytics`, `velato-engine`.
- Tests: `test_poison_message.py` (classification logic in isolation), plus a per-worker smoke test confirming the shared helper is actually wired in (not a full Kafka integration test per worker — that's PR5's job).

**PR4 — Poison-message, Go**:
- Files: `services/internal/kafkautil/consumer.go` (extended `Consume` signature), `services/realtime-gateway/main.go` (new producer wiring).
- Tests: Go unit test for the classification/DLQ-publish logic in `kafkautil`.

**PR5 — Recovery-drill CI job** (depends on PR1-4 all merged):
- Files: `.github/workflows/ci.yml`.
- Tests: the entire §24.9 exercise IS the test — this PR's job is standing up the drill itself.

**Cross-cutting, any PR touching it**: `recovery/recovery-matrix.json` (update `external_blockers` as items get proven), `TODOS.md` (already has the `SIGNALCHORD_ENV` entry from this review).

### 24.11 Risks

- **RPO-vs-availability tradeoff resolved, but the full-quiesce cadence still means real (if infrequent, e.g. daily) downtime** — needs explicit sign-off on the actual cadence number, not just the two-tier design.
- **Cluster-context confirmation is a human-attention control, not a code guarantee** — an operator can still retype the wrong context by mistake. Documented as a residual risk (§NOT in scope: the fully airtight version is a cluster-level admission policy).
- **Neo4j beyond Kafka retention is unrecoverable** — a structural limitation of the architecture, not a bug this feature introduces or can fully close.
- **Notification-worker's Expo error classification only handles one known-permanent code** — an unrecognized future Expo error stays classified transient (safe default: crash-loop-retry, not silently dropped), but isn't a complete provider taxonomy.
- **PR3 (poison-message Python) is the largest single PR** — a shared helper plus 9 worker wire-ups; splitting further would mean shipping a helper nothing uses yet, which is worse for reviewability, not better.

### 24.12 Acceptance criteria

1. A scheduled CronJob produces a real Postgres backup at least every 15 minutes with zero app downtime, landing in a dedicated MinIO bucket.
2. A scheduled full backup (Postgres + MinIO + Neo4j) runs on a longer, explicitly-agreed cadence.
3. `restore-v1.sh` (both full and `--postgres-only` paths) refuses to run against a namespace lacking the explicit restore-target annotation, and requires a retyped cluster-context confirmation.
4. A restored environment attempts zero real SMTP or Expo push calls (asserted against stub endpoints in the CI drill).
5. `replay-kafka.sh` resets a named consumer group's offsets to a controlled point and logs the before/after state to the recovery evidence report.
6. All 10 Kafka consumers isolate a `ValueError`-classified poison message to its `.dlq` topic instead of blocking the partition, verified per-consumer.
7. Replaying `alert.created.v1` for an already-processed alert produces exactly one alert row and zero duplicate Expo-push/email sends.
8. A CI check fails a PR introducing a destructive migration pattern without explicit acknowledgment.
9. The `recovery-drill` CI job runs the full §24.9 sequence end to end and produces a versioned recovery evidence report matching `recovery-matrix.json`'s schema.
10. No existing test regresses.
11. `recovery-matrix.json`'s `external_blockers` is updated to remove items this feature actually proves.

### 24.13 Recommended command to begin Phase 1 (PR1)

`/plan-eng-review` has now run twice on this spec (initial + this finalization pass) with 0 unresolved decisions. Next: implement PR1 directly — no further planning skill needed before code. Suggested kickoff: "Approved. Implement PR1 (backup automation + restore safety) exactly as specified in §24.10, following the phased approach, committing after each completed piece, running relevant tests continuously."

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | not run (401, Claude subagent substituted) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAR | 11 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run (backend/infra-only feature) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

**CROSS-MODEL:** Pass 1 surfaced 3 substantive tensions (backup/restore path mismatch, cluster-context blind spot, poison-message extraction effort) — all resolved, folded into §22/§23. The outside voice's broader "split into 5 PRs" scope verdict was reconsidered in this pass 2 finalization: **partially adopted as PR packaging** (§24.10, 5 sequential PRs off this one branch/feature) without reopening the underlying scope decision (all 7 phases stay in scope, Step 0's "proceed as scoped" still stands — this is about reviewability of delivery, not what gets built).
**VERDICT:** ENG CLEARED — ready to implement. §24 is the authoritative implementation plan.

NO UNRESOLVED DECISIONS
