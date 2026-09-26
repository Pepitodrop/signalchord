# Recovery Drill (CI) Runbook

`.github/workflows/recovery-drill.yml` is an automated, disposable-cluster rehearsal
of the backup/restore/replay/poison-message tooling described in
`docs/specs/recovery-and-replay-hardening.md` §24. It builds the real service
images, installs the real Helm charts into a throwaway `kind` cluster, and runs
the real scripts from `scripts/single-server/` and `scripts/recovery-drill/`
against them — nothing is mocked or dry-run. It is a CI rehearsal of the
mechanics, not a substitute for the staging/production drills still tracked in
`docs/release-checklist.md` §6 and `recovery/recovery-matrix.json`'s
`external_blockers`.

## When it runs

- Automatically on any pull request that touches the paths listed in the
  workflow's `on.pull_request.paths` (the backup/restore/replay scripts, the
  Helm charts, the poison-message code paths, `apps/control-plane`, and the
  workflow file itself).
- On demand via the Actions tab: **Recovery Drill** → **Run workflow**
  (`workflow_dispatch`).
- Superseded runs on the same branch/ref are cancelled automatically
  (`concurrency` with `cancel-in-progress: true`).

It does not run on every PR — this keeps standard CI fast. If you're changing
something in a covered path and don't see it trigger, check the `paths` filter
first.

## What it does

One job, in order (see the workflow file for exact commands):

1. Build the 7 SignalChord images and load them into a fresh `kind` cluster.
2. Install `signalchord-community` and `signalchord` (the same Helm charts used
   in production, `--set storageClassName=standard` to match kind's default
   StorageClass) into an isolated, per-run namespace (`signalchord-drill-<run
   id>`), and confirm all workloads roll out healthy.
3. Seed two tenants and capture a deterministic PostgreSQL baseline (per-table
   row count + `md5(string_agg(id, ...))` checksum).
4. Run `backup-postgres-only.sh` (asserting the control-plane deployment is
   never scaled to zero) and then the full `backup.sh`.
5. Stand up a second, empty namespace (`signalchord-restore-drill-<run id>`) —
   this namespace never receives seed data, standing in for "data loss."
6. Confirm `restore.sh` (`restore-v1.sh`) refuses to run against that namespace
   before it carries the `signalchord.io/restore-target: allowed` annotation,
   then annotate it and run the real restore.
7. Verify the restored PostgreSQL data matches the baseline exactly, table by
   table, and that `rails db:migrate:status` reports no pending migrations.
8. Produce an `alert.created.v1` event, let it process, reset the consumer
   group's offset backward with `replay-kafka.sh`, and confirm redelivery does
   not create a duplicate `alerts` row (idempotent `find_or_initialize_by`).
9. Inject a permanent Python poison message (unsupported `mutation_type`) into
   `graph.mutation-requested.v1`, followed by a healthy message on the same
   partition key. Confirm the poison message lands on
   `graph.mutation-requested.v1.dlq` with the required envelope metadata, the
   committed offset advances past it, and the healthy message is processed.
10. Repeat the same shape of check for a permanent Go poison message on
    `graph.mutation-completed.v1` (realtime-gateway).
11. Inject a transient-failure-shaped message on `claim.extracted.v1` and
    confirm it is never published to a DLQ and never advances the committed
    offset.
12. Always (`if: always()`): tear down the kind cluster, build the recovery
    evidence artifact from whatever section files exist, and upload both the
    evidence JSON and captured logs as workflow artifacts — even if an earlier
    step failed or the job timed out.

## Reading the evidence artifact

Each run uploads `recovery-evidence-<run id>` containing
`recovery-evidence.json` (schema in `scripts/recovery-drill/build_evidence.py`)
plus the raw logs. Start with two fields:

- `overall_result`: `"pass"` or `"fail"`.
- `failed_assertions`: a sorted list of `"<section>.<field>"` or
  `"<section>: <message>"` strings — this is the fastest way to find what
  broke without reading the whole file.

Each section (`backup`, `restore`, `replay`, `python_poison_message`,
`go_poison_message`, `transient_failure`, `duplicate_suppression`, `cleanup`)
carries its own result field(s) and, where relevant, a `failures` list with
human-readable detail. A section that's an empty `{}` means that stage of the
workflow never ran (e.g. because an earlier step crashed) — check the job logs
for that stage, not the evidence file.

## Debugging a failing run

1. Open the failed run in the Actions tab and check which step failed first —
   steps run in the order listed above, and a step's own `run:` log almost
   always shows the real error (a failed `helm upgrade --wait`, a nonzero
   script exit, a failed assertion) before the evidence-building step ever
   runs.
2. Download the `recovery-evidence-<run id>` artifact for the full evidence
   JSON and the `logs/` directory (`backup-full.log`, `backup-postgres-only.log`,
   `restore-negative.log`, `restore-positive.log`, `replay.log`).
3. Cleanup always runs, so a failed run never leaves a kind cluster behind on
   the runner — there is nothing to manually tear down.
4. If a step fails only intermittently, check the fixed `sleep` waits used
   between producing a message and consuming/asserting on it (8-20s,
   documented next to each `sleep` in the workflow) — a consistently slow
   runner could need those bumped, but treat that as a real signal before
   assuming flakiness.

## Known limitations

- Runs against a disposable `kind` cluster with locally built images, not
  against managed PostgreSQL/Kafka or any staging/production environment —
  see `recovery/recovery-matrix.json`'s `external_blockers` for what remains.
- The full `backup.sh`/`restore.sh` bundle includes Neo4j, object storage
  (MinIO) and secrets, but this drill's automated verification only
  reconciles PostgreSQL row counts and checksums; it does not assert on
  restored graph, object, or secret content.
- `backup-postgres-only.sh` is exercised end-to-end (creation, no-downtime
  assertion); it is not restored from and re-verified separately from the
  full-backup restore path in this drill.
- "Simulated data loss" is a namespace that was never seeded, not a
  destructive wipe of the original namespace's live data.
