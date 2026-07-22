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
4. **Async/reliable job infrastructure.** Sidekiq is configured but not running anywhere (no worker process in docker-compose); `TODOS.md` already documents this as deliberately deferred. This feature does not stand it up.

## 4. Recommended minimum viable alert experience

Confirmed with the user (all recommended options):

- **Feed scope**: organization-scoped, not watchlist-filtered. The existing `GET /api/v1/alerts` sort/shape is kept; sorting/prioritization uses the real existing fields (`alert_score` desc as primary key, `severity_code` desc as tiebreaker — both already on the model, no new column).
- **Confidence**: not displayed as a numeric confidence value. `alert_score`/`severity_code` are relabeled in the UI as "prioritization score"/"severity" (what they actually are), with no separate confidence claim anywhere.
- **Evidence depth**: "N evidence records referenced" + the raw ID list, replacing today's bare unlabeled `<pre>` dump — same underlying data, honestly framed, no fabricated content.
- **Policy linkage**: shown where real — `Alert.policy_id` (real FK) resolves to `Policy#name`, plus `policy_trace` (jsonb: `policy_id`, `policy_version_id`, `execution_engine`, `policy_source_sha256` — confirmed these 4 keys are the ones the internal controller actually populates today; `trace_hash`/`instructions_executed` are named in the `.slice(...)` call but never present in the actual upstream payload, so they're always absent — a small pre-existing dead-key issue worth fixing while touching this line, not worth a separate spec item).
- **Real-time**: SSE stays out of scope (existing cookie-auth limitation, already gracefully degrading to "Offline" per `main.tsx:391-397`). Add simple client-side polling (`setInterval`, 30s) to the alert feed view so it still refreshes over time without depending on the broken SSE path — this is the "normal API loading provides a correct usable feed" option the brief explicitly allows.
- **Email notification**: Rails-only, synchronous, triggered from the same request that already enqueues the push notification (`Internal::V1::AlertsController#create`). New `alert_email_deliveries` table for dedup/tracking. New `email_alerts_enabled` boolean on `Membership`, default `false` (opt-in).
- **"Qualifying alert"**: identical condition to the existing push path — newly created (`created`) and not suppressed (`!alert.suppressed?`). No new fabricated threshold.

## 5. Backend changes

**Models:**
- `Membership`: add `email_alerts_enabled:boolean, null: false, default: false`.
- New `AlertEmailDelivery` model (`apps/control-plane/app/models/alert_email_delivery.rb`): `belongs_to :organization`, `belongs_to :alert`, `belongs_to :membership`. `STATUSES = %w[pending delivered failed]`. Validates `status` inclusion, presence.
- `Policy`: no schema change; add a `display_name` helper only if needed for serialization (likely just use `name` directly).

**Controllers:**
- `Internal::V1::AlertsController#create`: after the existing `enqueue_notification` call, add `send_email_notifications(alert) if created && !alert.suppressed?` — loops over `alert.organization.memberships.enabled.where(email_alerts_enabled: true)`, for each: `AlertEmailDelivery.find_or_initialize_by(alert:, membership:)`, guarded by `new_record?` (idempotent — replays or duplicate calls never re-send), sets `status: "pending"`, `save!`, then attempts `AlertMailer.alert_notification(membership.user, alert).deliver_now` inside a `rescue StandardError` (mirrors `User#send_verification_email!`'s swallow-and-log pattern exactly) that updates the delivery row to `status: "delivered"` or `status: "failed", last_error: ...` — **never re-raises**, so a mail failure can never break alert creation or the push-notification path (confirmed necessary: `services/alert-projector/worker.py`'s uncaught-exception-crashes-and-Kafka-redelivers behavior means a raised exception here would crash the projector, and replaying the same `alert.created.v1` event afterward would hit `find_or_initialize_by(stable_id:)` and find the existing alert — `created` would be `false` on replay, so the notification/email path would silently never fire on retry; letting failures propagate would therefore make things worse, not better).
- `Api::V1::MembershipsController` (or wherever the current user manages their own membership — check `apps/control-plane/app/controllers/api/v1/` for the existing self-service membership endpoint, extend it) or a new minimal `Api::V1::NotificationPreferencesController` with `PATCH` for `email_alerts_enabled` scoped to the caller's own membership (never another user's) — exact home decided during implementation by following whichever existing self-service pattern is closest.
- `Api::V1::AlertsController#index`/`#show`: no route change; response now includes real fields only (no new fabricated fields). Confirm the existing `.order(created_at: :desc)` gets a documented, deliberate change to `.order(alert_score: :desc, severity_code: :desc)` for real prioritization (still overridable by `?unread=true`; keep `created_at` as a stable tiebreaker after severity).

**Mailer:**
- New `AlertMailer#alert_notification(user, alert)` (`apps/control-plane/app/mailers/alert_mailer.rb`), subject e.g. "New SignalChord alert: {alert.title}". HTML + text views. No shared mailer layout exists today (`OnboardingMailer` has none either) — this feature does not introduce one; each view stays self-contained, matching the existing convention.

## 6. Frontend changes

- `apps/web/src/main.tsx`: `Alerts`/`AlertList`/`Overview` — relabel "Score" as "Prioritization score", replace the bare evidence/graph-path `<pre>` dump with "N evidence records referenced" (count) + a collapsible raw-ID list, add the resolved policy name (from a new `policy_name`/`policy` field the alert serializer must expose — see §5) plus the real `policy_trace` keys, add honest empty/degraded states: "No alerts yet" (empty), "Prioritization pending" is not needed (alerts only ever appear once fully scored, no partial state exists upstream), "Evidence data unavailable" only if `evidence_ids` is empty (not an error — a genuinely empty list is a legitimate outcome, not degraded).
- Add 30s `setInterval`-based polling to the alerts view's `reload()` (cleared on unmount), replacing reliance on the broken SSE trigger for freshness — SSE trigger stays as an opportunistic optimization (already degrades gracefully), polling is the guaranteed floor.
- New small preferences UI: a toggle for `email_alerts_enabled`, placed in the existing dashboard shell (no new route needed — reuse the `View` union / nav pattern already established, e.g. a small section inside an existing settings-adjacent view, or a new minimal `"preferences"` view tab if none exists — confirm during implementation by checking whether a settings tab already exists, per the frontend research: it does not, so this adds one new nav item).
- `packages/api-client/src/index.ts`: extend `AlertRecord` type with the exposed `policy_name`/resolved policy_trace fields; add `updateMembershipPreferences(...)` or equivalent method for the new preference toggle.

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

## 8. Notification and email design

- **Trigger point**: `Internal::V1::AlertsController#create`, same request that already enqueues the push `OutboxEvent`, same qualifying condition (`created && !alert.suppressed?`).
- **Fan-out**: one email attempt per enabled membership in the alert's organization (`organization.memberships.enabled.where(email_alerts_enabled: true)`) — not one email per alert regardless of preference; a member who never opted in never receives anything, ever.
- **Delivery**: synchronous `AlertMailer.alert_notification(...).deliver_now`, wrapped in `rescue StandardError`, never re-raised (see §5 for why re-raising would be actively harmful given the Kafka-redelivery/idempotent-upsert interaction).
- **Content**: alert title, prioritization score/severity, resolved policy name (where `policy_id` present), evidence count, link to the alert in the web app (`/` — no deep-linkable alert detail route exists since this app has no router; link to the dashboard root, consistent with how the rest of this app has no per-record URLs).

## 9. Deduplication and retry design

- **Dedup**: DB-level unique index `[alert_id, membership_id]` on `alert_email_deliveries`, enforced identically to `NotificationDelivery`'s `[notification_endpoint_id, event_id]` pattern. `find_or_initialize_by(alert:, membership:)` + `new_record?` guard means a replayed `alert.created.v1` event, or any accidental double-call, can never send a second email for the same (alert, member) pair — matches "do not send duplicate emails" exactly.
- **Retry model — honest scope**: this feature does **not** add automatic background retry (no job infra is stood up, matching the TODOS.md-documented deferral). A failed send is recorded (`status: "failed", last_error: ..., attempts: attempts + 1`) and is **visible** (surfaced via the alert's serialized response, and/or a small internal query — exact surfacing decided in implementation, at minimum a Rails console/rake-task-queryable state) but not silently dropped, satisfying "do not silently swallow delivery failures" without inventing a retry pipeline that doesn't exist elsewhere in this codebase. A manual re-attempt (rake task or repeat internal call) is safe to run any number of times because of the dedup index — re-running only affects rows still in `pending`/`failed` state (a `delivered` row is left untouched, so manual retries can never double-send).
- **Why not real automatic retry**: confirmed via `services/alert-projector/worker.py` that Kafka-level redelivery of `alert.created.v1` — the only "free" retry mechanism available without new infra — would not even re-attempt this logic on replay, since `find_or_initialize_by(stable_id:)` on the Alert itself would short-circuit `created` to `false`. True automatic retry would require new job/queue infrastructure, which is out of scope per "if no real background pipeline exists, do not invent one."

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
| Request | `Internal::V1::AlertsController#create` — email fan-out: sends exactly one email per opted-in membership, sends zero when no membership opted in, never sends for a suppressed alert, never re-sends on a repeated create call with the same `stable_id` (idempotency), a mailer exception is caught and recorded as `failed` without raising/affecting the alert row or the push-notification enqueue | +5 |
| Request | Preference update endpoint — updates only the caller's own membership, rejects a client-supplied membership/user id for another member, tenant-isolated | +3 |
| Mailer | `AlertMailer#alert_notification` — recipient, subject, body includes title/score/policy name where present, omits policy section when `policy_id` is nil | +3 |
| Frontend unit | Pure-function extraction for: prioritization sort comparator, evidence-count/label derivation, poll-interval-driven reload logic (DOM-free, matching this codebase's established test convention — no component-rendering tests) | +3 |
| E2E (Playwright) | Extend an existing or add a new flow: seed an alert via the internal endpoint in test setup (or via existing fixtures), verify it appears in the feed sorted correctly, verify detail view shows honest evidence-count/no-confidence framing, verify enabling the email preference and receiving exactly one Mailpit email for a new qualifying alert (reusing the existing Mailpit helper from `e2e/tests/helpers/mailpit.ts`) | +1 flow |
| Tenant isolation | Extend `tenant_isolation_spec.rb`: `AlertEmailDelivery` not readable/writable cross-tenant, preference update cannot target another org's membership | +2 |

## 12. Phased implementation plan

1. **Phase 1 — backend**: migrations, `Membership#email_alerts_enabled`, `AlertEmailDelivery` model, `AlertMailer`, `Internal::V1::AlertsController` email fan-out, `Api::V1::AlertsController` sort-order change + serializer additions (`policy_name`, cleaned-up `policy_trace` slice), preference-update endpoint. Tests alongside, per §11 backend rows.
2. **Phase 2 — frontend**: relabeled alert feed/detail (prioritization score, evidence count, policy name), 30s polling, preference toggle UI. Tests alongside (pure-function extraction).
3. **Phase 3 — e2e**: extend Playwright coverage per §11's e2e row.
4. **Phase 4 — verification**: `pnpm typecheck && pnpm lint && pnpm test && pnpm build` locally; Rails specs, RuboCop-equivalent, and the full e2e run verified via CI (no Ruby/Docker in this sandbox, same constraint as the prior two features).

## 13. Files likely to change

| File | Change |
|---|---|
| `apps/control-plane/db/migrate/008_add_email_alerts_enabled_to_memberships.rb` | New migration |
| `apps/control-plane/db/migrate/009_create_alert_email_deliveries.rb` | New migration |
| `apps/control-plane/app/models/membership.rb` | New column (no code change needed beyond schema unless validating) |
| `apps/control-plane/app/models/alert_email_delivery.rb` | New model |
| `apps/control-plane/app/mailers/alert_mailer.rb` | New mailer |
| `apps/control-plane/app/views/alert_mailer/alert_notification.html.erb` / `.text.erb` | New views |
| `apps/control-plane/app/controllers/internal/v1/alerts_controller.rb` | Add email fan-out after existing `enqueue_notification` |
| `apps/control-plane/app/controllers/api/v1/alerts_controller.rb` | Sort order, serializer additions |
| `apps/control-plane/app/controllers/api/v1/*` (preference endpoint — exact controller decided in implementation) | New action or new controller |
| `apps/control-plane/config/routes.rb` | New preference route |
| `apps/control-plane/spec/models/alert_email_delivery_spec.rb` | New |
| `apps/control-plane/spec/requests/alerts_spec.rb` | New |
| `apps/control-plane/spec/requests/internal_alerts_spec.rb` (or extend existing) | New/extended |
| `apps/control-plane/spec/mailers/alert_mailer_spec.rb` | New |
| `apps/control-plane/spec/requests/tenant_isolation_spec.rb` | Extended |
| `apps/web/src/main.tsx` | Alert feed/detail relabeling, polling, preference toggle |
| `apps/web/src/routes/*.ts` (new pure-function files, naming TBD in implementation) | New, test-only extraction |
| `packages/api-client/src/index.ts` | `AlertRecord` field additions, preference method |
| `e2e/tests/*.spec.ts` | New or extended flow |
| `TODOS.md` | Optional one-line housekeeping fix for the stale SSE-cookie-limitation reference in `main.tsx:391-397` (comment claims tracking that isn't actually there) |

## 14. Acceptance criteria

1. `GET /api/v1/alerts` returns alerts sorted by `alert_score` desc, `severity_code` desc, `created_at` desc as a stable tiebreaker.
2. Alert detail view shows title, summary, prioritization score/severity (never labeled "confidence"), evidence count + raw IDs, resolved policy name where `policy_id` is present, and an honest "no policy linkage" state where it is nil.
3. A new alert for an organization with zero opted-in memberships sends zero emails.
4. A new alert for an organization with N opted-in memberships sends exactly N emails, one per member, never more than one per (alert, member) pair even under a replayed/duplicated internal create call.
5. A suppressed alert never triggers an email, matching the existing push-notification behavior.
6. A mailer exception during send is caught, recorded as `status: "failed"` with `last_error` populated, and does not affect the alert row, the push-notification enqueue, or the internal endpoint's response status.
7. The email preference toggle updates only the calling user's own membership; a request attempting to target another membership/user is rejected.
8. The alert feed view refreshes at least every 30 seconds via polling, independent of SSE connectivity state.
9. All new Postgres objects (`email_alerts_enabled`, `alert_email_deliveries`) are additive; no existing endpoint's response shape loses a field or changes an existing field's meaning.
10. Tenant isolation holds for every new/changed endpoint and table (verified by extended `tenant_isolation_spec.rb`).
11. `pnpm typecheck && pnpm lint && pnpm test && pnpm build` pass locally; all CI checks (including `rails`) pass on the opened PR.

## 15. Recommended next gstack command

`/plan-eng-review` — this spec introduces a new cross-cutting mailer/delivery-tracking pattern (`AlertEmailDelivery`) and a controller-level fan-out loop inside an internal, unauthenticated-by-user endpoint; an engineering review pass on the exact swallow/rescue boundaries and the sort-order change to a public API before implementation starts is worth the cheap up-front cost, matching the pattern used for the closed-beta onboarding feature.
