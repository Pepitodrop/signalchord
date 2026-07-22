## Explainable alert feed and notifications

Branch: `feature/explainable-alert-feed`
Base: `main` @ `dcb3f19` (PR #92, first-watchlist-setup, merged)
Status: specification — implementation not yet started

## 1. What already exists

**`Alert` model — real, not a stub.** `apps/control-plane/app/models/alert.rb` + migration `apps/control-plane/db/migrate/002_create_control_plane.rb:95-113`. Columns: `stable_id`, `title`, `summary`, `alert_score` (int 0-100), `severity_code` (int 0-9), `routing_code` (int, default 1), `suppressed` (bool), `evidence_ids`/`graph_path_ids` (jsonb string arrays), `policy_trace` (jsonb), `review_status` (string, default `"unreviewed"`, no formal enum — "verified"/"dismissed" are conventions enforced only by the frontend), `relevance_feedback`, `read_at` (nullable datetime), real FK `policy_id` → `policies` (nullable), real FK `organization_id` (not null). Unique index on `[organization_id, stable_id]`.

**Alert generation is a live, wired Kafka pipeline**, not dormant code:
`services/nlp-pipeline` (extracts entities/claims/relations from a document, publishes `alert.policy-evaluation-requested.v1`) → `services/velato-engine` (executes the actual Velato policy program, publishes `alert.created.v1`) → `services/alert-projector` (consumes `alert.created.v1`, `POST /internal/v1/alerts`) → `Internal::V1::AlertsController#create` (`apps/control-plane/app/controllers/internal/v1/alerts_controller.rb`) upserts the Postgres `Alert` row via `find_or_initialize_by(stable_id:)`, and — if newly created and not suppressed — enqueues a `notification.requested.v1` `OutboxEvent`.

**Push notification pipeline is fully wired.** `OutboxEvent`/`Outbox::Publisher` (poll-and-publish, `SELECT ... FOR UPDATE SKIP LOCKED`) → Kafka → `services/notification-worker` consumes `notification.requested.v1`, claims `NotificationEndpoint` rows (Expo/iOS/Android device tokens, `apps/control-plane/app/models/notification_endpoint.rb`) via `Internal::V1::NotificationTargetsController`, delivers Expo push, records `NotificationDelivery` (`apps/control-plane/app/models/notification_delivery.rb`) with a `[notification_endpoint_id, event_id]` unique index for dedup.

**Frontend alert feed and detail view already exist**, rendering real data — `apps/web/src/main.tsx:115-195` (`Overview`, `AlertList`, `Alerts`). API client methods already exist (`packages/api-client/src/index.ts:91-92`, `alerts()`/`updateAlert()`). Read/acknowledged state already exists and works: `read_at` + `review_status` set via real "Verify"/"Dismiss" buttons (`main.tsx:187-188`) calling `PATCH /api/v1/alerts/:id`.

**API endpoints**: `GET/PATCH /api/v1/alerts`, `/api/v1/alerts/:id` (`apps/control-plane/app/controllers/api/v1/alerts_controller.rb`) — tenant-scoped via `current_organization.alerts...`, `require_scope!("api:write")` on update, no `require_role!`. `POST /internal/v1/alerts` (shared-secret auth, tenant asserted by the caller via `tenant_id` in the event body — this is standard for this codebase's internal/service-to-service boundary, not a new gap).

**Email infra**: only `OnboardingMailer#verification_email` (`apps/control-plane/app/mailers/onboarding_mailer.rb`), synchronous `deliver_now`, swallow-and-log on failure (`apps/control-plane/app/models/user.rb:29-40`). `config.active_job.queue_adapter = :sidekiq` is configured but unused — no `deliver_later` call exists anywhere, and `TODOS.md:5-15` documents this as a deliberate, reviewed tradeoff (not an oversight) to avoid standing up async infra at current beta volume.

**Tests that exist today**: `spec/requests/tenant_isolation_spec.rb` (alert cross-tenant read/patch isolation, notification-delivery cross-tenant isolation), `spec/requests/governance_requests_spec.rb` (alerts as tenant-export/deletion side effects), `spec/requests/product_operations_spec.rb` (notification-endpoint auto-disable on invalid token). **Missing**: no `spec/models/alert_spec.rb`, no `spec/requests/alerts_spec.rb` (no dedicated test of the public alerts API or the internal create endpoint), no frontend tests for the alert feed/detail components.

## 2. What is operational versus only modeled

| Capability | Status |
|---|---|
| Alert creation from real pipeline events | **Operational** — live Kafka chain, confirmed via code (not just schema) |
| Alert read/update API, tenant isolation | **Operational** — tested (`tenant_isolation_spec.rb`) |
| Push notification delivery (Expo/iOS/Android) | **Operational** — full consumer chain, tested (`product_operations_spec.rb`) |
| Alert→Watchlist linkage | **Not modeled at all** — no column, no real matching logic upstream (see §3) |
| Confidence | **Not modeled at all** — no field exists anywhere in the pipeline |
| Evidence/graph-path content resolution | **Not modeled** — IDs exist, nothing resolves them to content (see §3) |
| Email notification | **Not modeled** — no mailer, no preference, no delivery tracking for email |
| Alert score/severity as a *trustworthy* signal | **Partially fabricated upstream, pre-existing, out of scope** — see below |

**Pre-existing upstream note (context, not something this feature touches):** `services/nlp-pipeline/worker.py:296-311` feeds the Velato policy engine partly hardcoded/synthetic inputs (`source_trust: 0.75`, `corroboration_count: 1`, `recency: 1.0`, `source_diversity: 0.4` — fixed constants, not derived from real signal) and a fake watchlist-match heuristic (`"Acme" in m.text`). This means `alert_score`/`severity_code` — while real, persisted, and already displayed — are not yet backed by fully real scoring inputs. This is a pre-existing data-pipeline quality issue, **not created by and not fixed by this feature** (fixing it means changing `services/nlp-pipeline`'s extraction/scoring logic, a separate, larger initiative). It is the reason this spec insists on labeling `alert_score`/`severity_code` honestly as "prioritization score/severity" rather than dressing them up as "confidence."

## 3. Missing upstream capabilities

1. **Alert↔Watchlist linkage.** No `watchlist_item_id`/`watchlist_id` column on `Alert`, and no upstream logic that would populate one meaningfully (the only "watchlist match" signal in the pipeline is the hardcoded `"Acme"` string check). Building a real linkage requires `services/nlp-pipeline` to actually resolve against an org's configured `WatchlistItem.target_stable_id`s — out of scope for this feature (would be inventing/rearchitecting the generation pipeline, explicitly disallowed).
2. **Confidence scoring.** `services/velato-engine/engine.py:122-126` (`PolicyResult`) has no confidence output. Adding one means changing the Velato policy IR/engine — out of scope.
3. **Evidence/graph-path content resolution.** `services/graph-query/app.py` exposes evidence only nested inside `GET /v1/entities/{stable_id}` (entity-scoped, capped at 50), and has no endpoint that takes a bare `evidence_id` or `relationship_id` and returns its content. Alerts aren't tied to a specific entity either, so even the entity-scoped endpoint isn't usable here. Building a real resolution endpoint is a `graph-query` change — out of scope.
4. ~~**Async/reliable job infrastructure.** Sidekiq is configured but not running anywhere.~~ **Superseded during `/plan-eng-review` (see §5/§8/§9 and the review report at the end of this document).** An outside-voice review pass found that keeping email delivery synchronous inside `Internal::V1::AlertsController#create` created two real bugs (a silent, unrecoverable notification-drop on any mid-loop crash, and cross-tenant head-of-line blocking through the single-consumer `alert-projector`), and that Sidekiq is already gem-installed and already configured as the `ActiveJob` queue adapter — only a worker process and a Redis-connection initializer were missing. This feature now stands up that worker process (mirroring the existing `bin/outbox-publisher` sidecar-process pattern exactly), closing this gap rather than deferring it a second time.

## 4. Recommended minimum viable alert experience

Confirmed with the user (all recommended options):

- **Feed scope**: organization-scoped, not watchlist-filtered. The existing `GET /api/v1/alerts` sort/shape is kept; sorting/prioritization uses the real existing fields (`alert_score` desc as primary key, `severity_code` desc as tiebreaker — both already on the model, no new column).
- **Confidence**: not displayed as a numeric confidence value. `alert_score`/`severity_code` are relabeled in the UI as "prioritization score"/"severity" (what they actually are), with no separate confidence claim anywhere.
- **Evidence depth**: "N evidence records referenced" + the raw ID list, replacing today's bare unlabeled `<pre>` dump — same underlying data, honestly framed, no fabricated content.
- **Policy linkage**: shown where real — `Alert.policy_id` (real FK) resolves to `Policy#name`, plus `policy_trace` (jsonb: `policy_id`, `policy_version_id`, `execution_engine`, `policy_source_sha256`). The `.slice(...)` call in `Internal::V1::AlertsController#create` also names `trace_hash`/`instructions_executed`, which the upstream `velato-engine` payload never actually sends (always absent, dead code) — since this feature is already touching this exact line for the transaction-wrap change, drop those 2 dead key names from the `.slice()` call in the same diff (confirmed during review, zero extra cost).
- **Real-time**: SSE stays out of scope (existing cookie-auth limitation, already gracefully degrading to "Offline" per `main.tsx:391-397`). Add simple client-side polling (`setInterval`, 30s) to the alert feed view so it still refreshes over time without depending on the broken SSE path — this is the "normal API loading provides a correct usable feed" option the brief explicitly allows.
- **Email notification**: triggered from the same request that already enqueues the push notification (`Internal::V1::AlertsController#create`), but the actual send happens in a new Sidekiq-backed `AlertEmailNotificationJob` (one job per recipient), not inline in the request — revised during `/plan-eng-review`, see §5/§8/§9. New `alert_email_deliveries` table for dedup/tracking. New `email_alerts_enabled` boolean on `Membership`, default `false` (opt-in).
- **"Qualifying alert"**: identical condition to the existing push path — newly created (`created`) and not suppressed (`!alert.suppressed?`). No new fabricated threshold.

## 5. Backend changes

**Revised during `/plan-eng-review`**: the original design ran the email fan-out inline inside `Internal::V1::AlertsController#create` (synchronous `deliver_now` in a loop). An outside-voice review pass found this created a silent, unrecoverable notification-drop bug and cross-tenant head-of-line blocking (full detail in the review report at the end of this document). The revised design below moves the actual send into a Sidekiq job; the controller only enqueues cheap jobs (fast DB/Redis writes, no SMTP calls block the request).

**Infrastructure (new):**
- `apps/control-plane/config/initializers/sidekiq.rb`: `Sidekiq.configure_server`/`configure_client` pointed at `ENV.fetch("REDIS_URL", "redis://localhost:6379/0")` — the `REDIS_URL` env var and the underlying Valkey (Redis-compatible) container already exist in `docker-compose.yml`/`docker-compose.override.yml` for other purposes; this is the first time Rails itself connects to it.
- New `sidekiq` service in `docker-compose.override.yml`, same image as `control-plane` (`infrastructure/docker/control-plane.Dockerfile`), `command: ["bundle", "exec", "sidekiq"]`, `depends_on: {control-plane: {condition: service_healthy}}` — this exactly mirrors the existing `outbox-publisher` service block (`docker-compose.override.yml:70-83`), which already establishes the "sidecar Ruby process, same image, different command" pattern for this app. No new deployment pattern is being invented.
- Gemfile already has `sidekiq ~> 8.0` (`apps/control-plane/Gemfile:13`) and `config.active_job.queue_adapter = :sidekiq` is already set (`apps/control-plane/config/application.rb:12`) — no Gemfile change needed.

**Models:**
- `Membership`: add `email_alerts_enabled:boolean, null: false, default: false`.
- New `AlertEmailDelivery` model (`apps/control-plane/app/models/alert_email_delivery.rb`): `belongs_to :organization`, `belongs_to :alert`, `belongs_to :membership`. `STATUSES = %w[pending sending delivered failed]` — the 4-state shape is deliberately copied from `NotificationDelivery::STATUSES` (`apps/control-plane/app/models/notification_delivery.rb:2`) rather than inventing a new shape; `"sending"` is the in-flight marker used to detect the narrow ambiguous-outcome window described below. Validates `status` inclusion, presence.
- `Policy`: no schema change; use `name` directly for serialization.

**Job (new):**
- `apps/control-plane/app/jobs/alert_email_notification_job.rb`: `AlertEmailNotificationJob < ApplicationJob`, `sidekiq_options retry: 5` (capped, not Sidekiq's 25-attempt/~3-week default — an alert email is time-sensitive context, a delivery attempt weeks late is close to useless; confirmed with the user during review). `perform(alert_id, membership_id)`:
  1. Load `alert` and `membership`; `delivery = AlertEmailDelivery.find_or_initialize_by(alert:, membership:)`.
  2. If `delivery.status == "delivered"`, return immediately (already sent — handles Sidekiq's at-least-once redelivery of the same job).
  3. If `delivery.status == "sending"` (found already in this state — meaning a previous run got far enough to attempt the send but never confirmed the outcome, the one gap raw SMTP without a provider-side idempotency key can't fully close), do **not** resend automatically: mark `status: "failed", last_error: "ambiguous outcome from a previous attempt — resend requires manual confirmation"` and return. This is an honest, disclosed limitation, not a silent gap — the alternative (blindly resending) risks a real duplicate; this trades a narrow, rare "needs a human to check" state for a guarantee of never double-sending.
  4. Otherwise: `delivery.update!(status: "sending")` (committed immediately, its own write), then `AlertMailer.alert_notification(membership.user, alert).deliver_now`. On success, `delivery.update!(status: "delivered")`. On any `StandardError`, `delivery.update!(status: "failed", last_error: error.message, attempts: delivery.attempts + 1)` and **re-raise** — unlike the synchronous design this supersedes, re-raising here is correct: Sidekiq's own retry mechanism (capped at 5 attempts) picks it up, instead of a hand-rolled swallow-and-log doing a worse job of the same thing.

**Controllers:**
- `Internal::V1::AlertsController#create`: wraps `alert.save!` and the existing push-notification `OutboxEvent.enqueue!` in one `ActiveRecord::Base.transaction` (closes a pre-existing gap found during review — these were previously two separate non-transactional statements, so a raised `enqueue_notification` failure today leaves the alert committed but the notification silently lost with no retry, since a Kafka redelivery would find the alert already persisted and skip the whole block). After that transaction commits, loop over `alert.organization.memberships.enabled.where(email_alerts_enabled: true)` and call `AlertEmailNotificationJob.perform_later(alert.id, membership.id)` for each — enqueueing only, no SMTP calls in this request at all. This loop needs no `.includes(:user)` (the N+1 concern raised during review): it only touches `membership.id`, and each job independently loads exactly the one `membership.user` it needs.
- `Api::V1::MeController#update` (new action, on the existing self-service `apps/control-plane/app/controllers/api/v1/me_controller.rb` — not a new controller; chosen during review over `Api::V1::MembershipsController` because that controller is `require_role!("owner", "admin")`-gated and built for admins managing *other* members, while `MeController` is already this app's unauthenticated-by-role "act on my own record" endpoint): updates `current_membership.email_alerts_enabled` only, never accepts a client-supplied membership/user id.
- `Api::V1::AlertsController#index`: `.order(created_at: :desc)` → `.order(alert_score: :desc, severity_code: :desc, created_at: :desc)` (severity as tiebreaker, `created_at` as the final stable tiebreaker), plus `.includes(:policy)` (found during review — serializing the new `policy_name` field without eager-loading would be an N+1 across up to 250 alerts).

**Mailer:**
- New `AlertMailer#alert_notification(user, alert)` (`apps/control-plane/app/mailers/alert_mailer.rb`), subject e.g. "New SignalChord alert: {alert.title}". HTML + text views. No shared mailer layout exists today (`OnboardingMailer` has none either) — this feature does not introduce one; each view stays self-contained, matching the existing convention.

## 6. Frontend changes

**Revised during `/plan-design-review`** — 6 design decisions resolved (detail-pane field order, loading state, toggle save behavior, evidence framing copy, toggle visual language, nav placement). See the review report at the end of this document.

- `apps/web/src/main.tsx`, `useAlerts` (`:25-63`): add an explicit `loading` boolean, `true` until the first fetch resolves. `AlertList` renders "Checking for alerts…" while `loading`, and only renders "No alerts yet" after a real, resolved, empty response — closes a false-empty flash the review found (`main.tsx` today shows "No alerts yet" the instant it mounts, before the first fetch completes, which directly contradicts this feature's own "never show fabricated output as real" premise).
- `Alerts` detail pane (`:157-195`) — **field order, specified**: title → summary → resolved policy name (or an honest "Not linked to a specific policy" when `policy_id` is nil) → evidence section → Verify/Dismiss actions. Matches the order a user would actually ask the questions ("what changed" → "why it matters" → "show me the proof").
  - "Score" relabeled "Prioritization score" (never "confidence").
  - Evidence section: "N evidence records referenced" as the visible summary, with a collapsed disclosure for the raw IDs labeled **"Raw evidence references (IDs only — content lookup not yet available)"** — not a bare, unframed dump. This turns a real limitation into a disclosed one instead of something that reads as broken (found during review: bare opaque IDs risk reading as "this app doesn't know anything" rather than as transparency).
  - Empty evidence (`evidence_ids: []`) shows "No evidence indexed yet for this one" as calm, muted text — a legitimate outcome, not an error state.
- Add 30s `setInterval`-based polling to the alerts view's `reload()` (cleared on unmount), replacing reliance on the broken SSE trigger for freshness — SSE trigger stays as an opportunistic optimization (already degrades gracefully), polling is the guaranteed floor.
- **Email preference toggle — placement and visual language, resolved during design review**: no new top-level nav tab (the original plan's "confirm during implementation" placeholder is replaced with a concrete decision). Desktop (≥900px): a small labeled control in the existing sidebar `<footer>` (`:430-434`, already shows org name/user/sign-out — account-adjacent, not a new concept). Mobile (<900px, where that footer is `display:none`): a small settings icon in the workspace header (`:437-442`, next to the existing Live/Offline badge) opens the same control. This avoids adding a 7th item to the 6-tab nav, which would both orphan a lone button on the mobile `nav{grid-template-columns:repeat(3,1fr)}` 3-column grid (confirmed in `styles.css`) and over-elevate a single boolean preference to the same wayfinding tier as the app's core workspaces.
  - Visual language: a labeled button (e.g. "Email alerts: On"/"Email alerts: Off", toggles on click), styled with the same `.actions` button classes already used for "Verify"/"Dismiss" — not a generic pill/switch component, since this app has no toggle-switch precedent anywhere and a labeled button pair matches its existing all-buttons interaction vocabulary. Keyboard nav and touch targets are inherited for free from the existing button convention (native `<button>`, already used everywhere).
  - Save behavior: optimistic update (flips immediately on click), `PATCH /api/v1/me` fires in the background; on failure, revert the toggle and show a small inline "Couldn't save — try again" message next to it.
- `packages/api-client/src/index.ts`: extend `AlertRecord` type with the exposed `policy_name`/resolved `policy_trace` fields; add an `updateMe(...)` or equivalent method (matching `Api::V1::MeController#update`) for the preference toggle.

## 7. Database / migration changes

Two purely additive migrations, both backward-compatible (no existing behavior changes for rows that don't opt in):

```ruby
# 008_add_email_alerts_enabled_to_memberships.rb
class AddEmailAlertsEnabledToMemberships < ActiveRecord::Migration[8.0]
  def change
    add_column :memberships, :email_alerts_enabled, :boolean, null: false, default: false
  end
end

# 009_create_alert_email_deliveries.rb
class CreateAlertEmailDeliveries < ActiveRecord::Migration[8.0]
  def change
    create_table :alert_email_deliveries, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :alert, type: :uuid, null: false, foreign_key: true
      t.references :membership, type: :uuid, null: false, foreign_key: true
      t.string :status, null: false, default: "pending"
      t.integer :attempts, null: false, default: 0
      t.text :last_error
      t.timestamps
    end
    add_index :alert_email_deliveries, %i[alert_id membership_id], unique: true, name: "idx_alert_email_delivery_dedup"
  end
end
```

No migration change from the Sidekiq revision — `status` stays a bare string column; the 4th state (`"sending"`) is an application-level value (`AlertEmailDelivery::STATUSES`), not a schema change.

## 8. Notification and email design

**Revised during `/plan-eng-review`** — see the rewritten §5 and the review report for why this moved off the original synchronous design.

- **Trigger point**: `Internal::V1::AlertsController#create` enqueues `AlertEmailNotificationJob.perform_later(alert.id, membership.id)` per opted-in membership, same qualifying condition as the push path (`created && !alert.suppressed?`). Enqueueing is a fast Redis write, not an SMTP call — the controller's response time is no longer coupled to recipient count or mail-provider latency at all, which also resolves the cross-tenant head-of-line-blocking risk the original design had (a slow/degraded mail provider can no longer stall every other organization's alert ingestion, since `alert-projector`'s HTTP call to `/internal/v1/alerts` never touches SMTP).
- **Fan-out**: one job, and therefore one email attempt, per enabled membership in the alert's organization with `email_alerts_enabled: true` — a member who never opted in never receives anything, ever.
- **Delivery**: `AlertMailer.alert_notification(...).deliver_now` inside `AlertEmailNotificationJob#perform` (already running in a background worker process, so `deliver_now` — not `deliver_later` — is correct; queuing a mailer job from inside a job would double-queue for no benefit).
- **Content**: alert title, prioritization score/severity, resolved policy name (where `policy_id` present), evidence count, link to the dashboard root (no deep-linkable alert detail route exists since this app has no router).

## 9. Deduplication and retry design

**Revised during `/plan-eng-review`.**

- **Dedup**: DB-level unique index `[alert_id, membership_id]` on `alert_email_deliveries`, enforced identically to `NotificationDelivery`'s `[notification_endpoint_id, event_id]` pattern. `find_or_initialize_by(alert:, membership:)` plus the job's own `status` state machine (see §5, step 2/3) means: a `"delivered"` row is never resent (handles Sidekiq's at-least-once job redelivery), and a job that died between "sent" and "confirmed" (the `"sending"` state found already set) is treated as ambiguous and surfaced for manual review rather than blindly resent — matches "do not send duplicate emails" for every case that can be distinguished, and is honest about the one narrow case (send succeeded, confirmation write failed) that raw SMTP without a provider-side idempotency key cannot fully resolve automatically.
- **Retry model**: real automatic retry, via Sidekiq's built-in mechanism, capped at 5 attempts (confirmed with the user — shorter than Sidekiq's 25-attempt/~3-week default, since alert emails are time-sensitive). This supersedes the original "no automatic retry, matches TODOS.md's deferred stance" position — the review found that position was compounding a debt TODOS.md already named the fix for (the onboarding mailer's own sync-SMTP-blocks-a-request problem), rather than avoiding scope creep.
- **Failure visibility**: a `"failed"` `AlertEmailDelivery` row (whether from an exhausted retry or an ambiguous-outcome detection) is queryable and does not silently disappear — exact UI/API surfacing of failed deliveries decided in implementation (at minimum, queryable via Rails console/a small internal query; a dedicated UI surface is not required by the acceptance criteria).
- **Why this no longer depends on Kafka redelivery semantics at all**: the original design's retry story was entangled with `alert.created.v1`'s redelivery-on-crash behavior (and the review found that entanglement was itself a bug — see the review report). Moving the send into a Sidekiq job fully decouples email retry from Kafka/alert-creation semantics: a job failing and retrying has no effect on whether the alert row exists or whether the push notification already fired.

## 10. Security and tenant-isolation risks

- All new queries scoped through `current_organization`/`alert.organization`/`membership.organization` — no new cross-tenant surface introduced (mirrors the existing pattern that `tenant_isolation_spec.rb` already tests for `Alert`/`NotificationDelivery`).
- The new preference-update endpoint must scope to **the calling user's own membership only** — never accept a client-supplied `membership_id`/`user_id` to mutate someone else's preference (matches "do not trust organization IDs from the client," extended here to "do not trust membership/user IDs from the client either").
- `Internal::V1::AlertsController` remains behind the existing shared-secret `authenticate_internal!` check — no change to that boundary; email-sending code added here does not introduce any new externally-reachable surface (it only runs as a side effect of the existing internal-only create action).
- CSRF/cookie-session/RBAC on the public `Api::V1::AlertsController` are unchanged — no relaxation.
- No PII beyond what's already handled (user email — already stored, already used for `OnboardingMailer`) is newly introduced.

## 11. Required tests

| Layer | What | Count (approx) |
|---|---|---|
| Model | `AlertEmailDelivery` validations, dedup uniqueness (scoped to alert+membership, allows same alert across different members) | +3 |
| Model | `Membership#email_alerts_enabled` default, column presence | +1 |
| Request | `spec/requests/alerts_spec.rb` (new — currently missing entirely): index sort order (`alert_score` desc), unread filter, show/update tenant isolation regression (already covered by `tenant_isolation_spec.rb`, add model-level coverage instead) | +4 |
| Request | `Internal::V1::AlertsController#create` — enqueues exactly one `AlertEmailNotificationJob` per opted-in membership, enqueues zero when no membership opted in, never enqueues for a suppressed alert, never enqueues on a repeated create call with the same `stable_id` (idempotency), `alert.save!` rolls back if `OutboxEvent.enqueue!` raises (new transaction wrap — regression-adjacent, this changes existing rollback behavior), `alert.save!` also rolls back if `AlertEmailNotificationJob.perform_later` raises (e.g. Redis unavailable — found during review's failure-mode pass, confirms the atomic-or-nothing behavior is real, not just assumed) | +6 |
| Job | `AlertEmailNotificationJob` — happy path sends and marks `delivered`; a `deliver_now` exception marks `failed` with `last_error` and re-raises (verify Sidekiq retry picks it up); a `"delivered"` row short-circuits with zero send attempts (redelivery-safe); a `"sending"` row is marked `failed` with the ambiguous-outcome message and does **not** attempt a send (the no-duplicate-send guarantee) | +4 |
| Request | `Api::V1::MeController#update` (new action) — updates only the caller's own membership, ignores/rejects a client-supplied membership/user id for another member, tenant-isolated, CSRF-checked (cookie-authed mutating request) | +4 |
| Mailer | `AlertMailer#alert_notification` — recipient, subject, body includes title/score/policy name where present, omits policy section when `policy_id` is nil | +3 |
| Frontend unit | Pure-function extraction for: evidence-count/framing-copy derivation (0/1/N cases, the disclosed-limitation copy), policy-name-or-honest-fallback derivation (DOM-free, matching this codebase's established test convention — no component-rendering tests) | +4 |
| E2E (Playwright) | Extend an existing or add a new flow: seed an alert via the internal endpoint in test setup (or via existing fixtures), verify the "Checking for alerts…" loading state appears before the feed renders, verify it appears in the feed sorted correctly, verify detail view shows fields in the resolved order (title → summary → policy → evidence) with honest evidence-framing/no-confidence copy, verify the email preference toggle (optimistic flip, revert-on-failure) and receiving exactly one Mailpit email for a new qualifying alert (reusing the existing Mailpit helper from `e2e/tests/helpers/mailpit.ts`) | +1 flow |
| Tenant isolation | Extend `tenant_isolation_spec.rb`: `AlertEmailDelivery` not readable/writable cross-tenant, preference update cannot target another org's membership | +2 |

## 12. Phased implementation plan

1. **Phase 1 — infra**: `config/initializers/sidekiq.rb`, new `sidekiq` service in `docker-compose.override.yml` (mirrors `outbox-publisher`). No product code yet — verify the worker process boots and connects to Redis/Valkey before building on top of it.
2. **Phase 2 — backend**: migrations, `Membership#email_alerts_enabled`, `AlertEmailDelivery` model, `AlertEmailNotificationJob`, `AlertMailer`, `Internal::V1::AlertsController` transaction wrap + job enqueueing, `Api::V1::AlertsController` sort-order change + `.includes(:policy)` + serializer additions, `Api::V1::MeController#update`. Tests alongside, per §11 backend/job rows.
3. **Phase 3 — frontend**: relabeled alert feed/detail (prioritization score, evidence count, policy name), 30s polling, preference toggle UI. Tests alongside (pure-function extraction).
4. **Phase 4 — e2e**: extend Playwright coverage per §11's e2e row.
5. **Phase 5 — verification**: `pnpm typecheck && pnpm lint && pnpm test && pnpm build` locally; Rails specs, RuboCop-equivalent, and the full e2e run (including the new `sidekiq` service actually running) verified via CI (no Ruby/Docker in this sandbox, same constraint as the prior two features).

## 13. Files likely to change

| File | Change |
|---|---|
| `apps/control-plane/config/initializers/sidekiq.rb` | New — Redis connection config |
| `docker-compose.override.yml` | New `sidekiq` service, mirroring `outbox-publisher` |
| `apps/control-plane/db/migrate/008_add_email_alerts_enabled_to_memberships.rb` | New migration |
| `apps/control-plane/db/migrate/009_create_alert_email_deliveries.rb` | New migration |
| `apps/control-plane/app/models/membership.rb` | New column (no code change needed beyond schema unless validating) |
| `apps/control-plane/app/models/alert_email_delivery.rb` | New model |
| `apps/control-plane/app/jobs/alert_email_notification_job.rb` | New job |
| `apps/control-plane/app/mailers/alert_mailer.rb` | New mailer |
| `apps/control-plane/app/views/alert_mailer/alert_notification.html.erb` / `.text.erb` | New views |
| `apps/control-plane/app/controllers/internal/v1/alerts_controller.rb` | Transaction wrap around `alert.save!`/push-enqueue, replace inline email send with per-membership job enqueue |
| `apps/control-plane/app/controllers/api/v1/alerts_controller.rb` | Sort order, `.includes(:policy)`, serializer additions |
| `apps/control-plane/app/controllers/api/v1/me_controller.rb` | New `update` action for the preference toggle |
| `apps/control-plane/config/routes.rb` | New `PATCH /api/v1/me` route |
| `apps/control-plane/spec/models/alert_email_delivery_spec.rb` | New |
| `apps/control-plane/spec/jobs/alert_email_notification_job_spec.rb` | New |
| `apps/control-plane/spec/requests/alerts_spec.rb` | New |
| `apps/control-plane/spec/requests/internal_alerts_spec.rb` (or extend existing) | New/extended |
| `apps/control-plane/spec/requests/me_spec.rb` | Extended (new `update` action tests) |
| `apps/control-plane/spec/mailers/alert_mailer_spec.rb` | New |
| `apps/control-plane/spec/requests/tenant_isolation_spec.rb` | Extended |
| `apps/web/src/main.tsx` | Alert feed/detail relabeling, polling, preference toggle |
| `apps/web/src/routes/*.ts` (new pure-function files, naming TBD in implementation) | New, test-only extraction |
| `packages/api-client/src/index.ts` | `AlertRecord` field additions, preference method |
| `e2e/tests/*.spec.ts` | New or extended flow |
| `TODOS.md` | Optional one-line housekeeping fix for the stale SSE-cookie-limitation reference in `main.tsx:391-397` (comment claims tracking that isn't actually there) |

## 14. Acceptance criteria

1. `GET /api/v1/alerts` returns alerts sorted by `alert_score` desc, `severity_code` desc, `created_at` desc as a stable tiebreaker.
2. Alert detail view shows, in order, title → summary → resolved policy name (or an honest "Not linked to a specific policy" fallback where `policy_id` is nil) → evidence section ("N evidence records referenced" + a collapsed "Raw evidence references (IDs only — content lookup not yet available)" disclosure, or "No evidence indexed yet for this one" when empty) → Verify/Dismiss actions. Score is always labeled "Prioritization score," never "confidence."
2a. The alert feed shows an explicit "Checking for alerts…" state until the first fetch resolves; "No alerts yet" only ever appears after a real, resolved, empty response — never on initial mount before data has loaded.
2b. The email preference toggle lives in the sidebar footer (desktop, ≥900px) and a header settings icon (mobile, <900px) — not as a 7th top-level nav tab. It is a labeled button matching the existing `.actions` button vocabulary (not a generic pill/switch), flips optimistically on click, and reverts with an inline "Couldn't save — try again" message if the `PATCH /api/v1/me` call fails.
3. A new alert for an organization with zero opted-in memberships enqueues zero `AlertEmailNotificationJob`s.
4. A new alert for an organization with N opted-in memberships enqueues exactly N jobs, one per member, and each job sends exactly once — never more than one delivered email per (alert, member) pair, even under Sidekiq's at-least-once job redelivery or a replayed/duplicated internal create call.
5. A suppressed alert never enqueues a push notification or an email job, matching the existing (extended) guard.
6. A job's `deliver_now` exception is recorded as `status: "failed"` with `last_error` populated and re-raised so Sidekiq retries it (capped at 5 attempts); it never affects the alert row, the push-notification enqueue, or `Internal::V1::AlertsController#create`'s response (the job is fully decoupled from the request/response cycle).
7. The email preference toggle (`PATCH /api/v1/me`) updates only the calling user's own membership; a request attempting to target another membership/user is rejected.
8. The alert feed view refreshes at least every 30 seconds via polling, independent of SSE connectivity state.
9. All new Postgres objects (`email_alerts_enabled`, `alert_email_deliveries`) are additive; no existing endpoint's response shape loses a field or changes an existing field's meaning.
10. Tenant isolation holds for every new/changed endpoint and table (verified by extended `tenant_isolation_spec.rb`).
11. If `OutboxEvent.enqueue!` (push notification) raises, the wrapping transaction rolls back `alert.save!` too — a Kafka redelivery of the same `alert.created.v1` event then retries cleanly instead of silently skipping the notification path forever.
12. The `sidekiq` docker-compose service boots successfully and processes a real job end-to-end in CI/local verification.
13. `pnpm typecheck && pnpm lint && pnpm test && pnpm build` pass locally; all CI checks (including `rails`) pass on the opened PR.

## TODOS.md updates (from `/plan-eng-review` and `/plan-design-review`)

Five items confirmed with the user to add to `TODOS.md` when implementation starts (a sixth candidate — the stale SSE-cookie-limitation comment — is built directly into this PR instead, not deferred):

1. **Real evidence/graph-path content resolution.** `services/graph-query` needs a bare evidence/relationship-by-ID lookup endpoint; today only entity-scoped resolution exists and `Alert` has no entity reference to hang it on. Biggest remaining honesty gap in the alert-explainability story. Depends on deciding how `Alert` would reference a specific entity/evidence set (doesn't today).
2. **Real Alert↔Watchlist linkage.** `services/nlp-pipeline` needs to match extracted entities against an org's actual `WatchlistItem.target_stable_id`s (replacing the current hardcoded `"Acme" in text` heuristic), plus a real `watchlist_item_id` FK on `Alert`. This is the literal premise of the feature's target journey, currently backed by zero real data. Depends on `nlp-pipeline` gaining a way to fetch an org's current watchlist items.
3. **Real confidence scoring.** `services/velato-engine`'s `PolicyResult` has no confidence field, and the scoring inputs feeding `alert_score` are partly synthetic. An open research question (what would real confidence even be computed from), not just an engineering task — bigger than items 1/2.
4. **Alert-email fan-out failure visibility UI.** A dedicated UI/API surface for viewing and manually retrying `failed` `AlertEmailDelivery` rows beyond the current console/internal-query-only visibility.
5. **Formal `DESIGN.md`.** No documented design system exists in this repo (confirmed during `/plan-design-review` — the second time this gap has been flagged across feature-level reviews). Every design review has to re-derive conventions from reading existing components rather than checking against a stated system. Not blocking — the app's design has stayed consistent without one so far — but worth establishing once broad UI patterns stabilize.
6. **`alert.policy_id` is never populated by the real pipeline (found during implementation).** `services/nlp-pipeline/worker.py:298` hardcodes `"policy_id": "default-watchlist-novelty"` — a human-readable slug, not the seeded `Policy` row's actual Postgres UUID (`db/seeds.rb:51` creates that row matched by `name:`, with an auto-generated `id`). `Internal::V1::AlertsController#create` correctly leaves `alert.policy_id` unset rather than risk a UUID type error assigning the slug directly — this is a deliberate choice, not an oversight, and the honest "not linked to a specific policy" fallback (already part of this spec) covers the resulting nil case correctly. Fixing this for real requires either the pipeline emitting a real Policy UUID, or a normalized slug↔Policy mapping — genuinely out of scope for this feature (touches `nlp-pipeline`/`velato-engine`, same category as items 2/3 above).

## 15. Recommended next gstack command

`/plan-eng-review` — this spec introduces a new cross-cutting mailer/delivery-tracking pattern (`AlertEmailDelivery`) and a controller-level fan-out loop inside an internal, unauthenticated-by-user endpoint; an engineering review pass on the exact swallow/rescue boundaries and the sort-order change to a public API before implementation starts is worth the cheap up-front cost, matching the pattern used for the closed-beta onboarding feature.

**Update after review: both `/plan-eng-review` and `/plan-design-review` have now run and cleared this spec** (see report below). Next: proceed to implementation.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 5 findings (2 architecture, 1 code quality, 2 performance), all resolved; 19 test gaps mapped to required tests + 1 added during failure-mode review |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR (score 5/10 → 8/10) | 6 design decisions resolved across 7 passes (field order, loading state, evidence-framing copy, toggle placement/vocabulary/save-behavior); 1 TODO (formal DESIGN.md) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

- **CODEX:** not run for either review — Codex CLI installed but not authenticated in this sandbox (401 Unauthorized on the API) in both the eng review and the design review. Both fell back to a Claude subagent per the documented fallback.
- **CROSS-MODEL (eng review):** The outside voice (Claude subagent, independent context, verified all load-bearing claims against the actual repo rather than trusting the plan's prose) found 3 problems the primary review missed: (1) the primary review's own transaction/dedup fix for duplicate-send prevention introduced a worse silent, unrecoverable notification-drop bug via the `created` guard on Kafka redelivery; (2) the accepted "bump the projector timeout" mitigation for synchronous email-send latency doesn't fix cross-tenant head-of-line blocking through the single `alert-projector` consumer, and arguably makes it worse; (3) strategic — building bespoke synchronous retry/dedup tracking compounds the exact sync-SMTP-blocks-a-request debt `TODOS.md` already named "stand up Sidekiq" as the fix for, on a different mailer, in this same codebase. User accepted the outside voice's recommendation on all three (folded into one architecture decision: move email delivery to a Sidekiq-backed `AlertEmailNotificationJob`), superseding the original "Rails-only synchronous" design locked in during `/spec`.
- **CROSS-MODEL (design review):** The outside-voice design subagent found a false-empty-state gap the primary design pass hadn't yet reached (the alert feed shows "No alerts yet" before the first fetch resolves, contradicting the feature's own "never fabricate" premise) and sharpened the nav-placement concern with a concrete mobile-grid-breakage detail. Both incorporated directly into the review passes rather than re-litigated.
- **VERDICT:** ENG REVIEW + DESIGN REVIEW CLEARED — ready to implement. CEO/DX reviews not run (optional; no significant product-direction or developer-experience gaps surfaced that would warrant them).

NO UNRESOLVED DECISIONS
