## Tenant security and abuse-control verification

Branch: `feature/tenant-security-hardening`
Base: `main` @ `a39e5fd` (PR #93, explainable-alert-feed, merged)
Status: specification — implementation not yet started

This spec covers a security-oriented repository analysis across the closed-beta product (PR #91 onboarding, PR #92 first-watchlist, PR #93 alert feed/notifications), proving or disproving tenant isolation, authorization correctness, and abuse resistance. Every finding below was reached by tracing actual code (models, controllers, migrations, config) — never inferred from route/controller names alone. Four parallel research passes covered: (1) organization-owned models/associations/DB constraints/race conditions, (2) every public + internal controller's auth/RBAC/CSRF/CORS/mass-assignment/logging behavior, (3) authentication/session mechanics and abuse paths (enumeration, fixation, flooding), (4) background jobs, Rack::Attack, existing test coverage, and CI security checks.

## 1. Current security architecture

- **Multi-tenancy**: every organization-owned table carries a real, DB-FK-backed `organization_id` (or, for `OutboxEvent`, `tenant_id` via `belongs_to :organization, foreign_key: :tenant_id`). Two tables (`watchlist_items`, `policy_versions`) have no direct org column but hang off a mandatory, non-optional parent (`Watchlist`, `Policy`) that itself carries the direct FK — no orphan-prone nullable path exists anywhere in the model layer. 20 models total, all traceable to an org.
- **Authentication**: dual-mode — Bearer token (`Authorization: Bearer sc_...`, mobile/API) and httpOnly encrypted cookie (`sc_session`, web), both ultimately backed by the same `ApiToken` model (`app/models/api_token.rb`). `ApplicationController#authenticate_api_token!` resolves either into `@current_api_token`, tags `@current_auth_source` (`:header`/`:cookie`), and rejects (401/403) invalid, expired, revoked tokens or disabled users/memberships — on every request, no caching beyond single-request memoization.
- **Authorization**: two independent primitives — `require_scope!(scope)` (checks the token's own `scopes` array, currently a point-in-time snapshot from issuance — see Blocker #2) and `require_role!(*roles)` (checks the *live* `current_membership.role`, re-read from the DB every call). `Membership::ROLES = %w[owner admin analyst reviewer viewer]`; `Membership.scopes_for` is the single, non-duplicated source of role→scope mapping (`owner`/`admin` → `["*"]`, `analyst`/`reviewer` → `["api:read","api:write"]`, `viewer` → `["api:read"]`).
- **CSRF**: Origin-header validation (`verify_same_origin!`), scoped to cookie-authenticated, non-GET/HEAD requests only. Header-authenticated (mobile) requests are never subject to it (correct — browsers never auto-attach a bearer header).
- **CORS**: `Rack::Cors` allow-listing `WEB_ORIGINS` (same env var, same parsing, as the CSRF check — no drift), `credentials: true`.
- **Internal service boundary**: `internal/v1/*` controllers inherit `ActionController::API` directly (not `ApplicationController`), gated by a single shared-secret header (`X-SignalChord-Internal-Token`) compared via `ActiveSupport::SecurityUtils.secure_compare`. Not reachable by an ordinary user's Bearer token or cookie session.
- **Rate limiting**: `Rack::Attack`, IP-keyed throttles on signup/login/verification/resend/org-creation, plus a global per-IP catch-all and a request-body-size blocklist. No safelist, no persistent-offender blocklist, **no configured durable store** (Blocker — see below).
- **Audit trail**: `AuditEvent` (org-scoped) records successful authorized mutations only. No record of denials.

## 2. Complete endpoint/authentication matrix

| Controller#action | Auth | `require_scope!` | `require_role!` | Tenant scoping |
|---|---|---|---|---|
| `Api::V1::AlertsController` #index/#show/#update | cookie/bearer | `update`: `api:write` | none | `current_organization.alerts` |
| `Api::V1::AuthController` #create | none (pre-auth) | n/a | n/a | resolves org by slug + membership |
| `Api::V1::EmailVerificationsController` #create/#resend | none (pre-auth) | n/a | n/a | none (pre-tenant) |
| `Api::V1::EntitiesController` #show/#timeline/#graph | cookie/bearer | none | none | proxies to graph-query with `tenant_id` param (isolation delegated downstream) |
| `Api::V1::GovernanceRequestsController` #index/#show/#create | cookie/bearer | `create`: `api:write` | **none** (Blocker #1) | `current_organization.governance_requests` |
| `Api::V1::InvestigationsController` full CRUD | cookie/bearer | write actions: `api:write` | none | `current_organization.investigations` |
| `Api::V1::InvitationsController` #index/#create/#destroy | cookie/bearer | none | `owner`/`admin` | `current_organization.invitations` |
| `Api::V1::InvitationsController` #accept | none (pre-auth, token-based) | n/a | n/a | derives org from invitation |
| `Api::V1::MeController` #show/#update | cookie/bearer | none | none | `current_membership` (server-derived only) |
| `Api::V1::MembershipsController` full | cookie/bearer | none | `owner`/`admin` (all actions) | `current_organization.memberships` |
| `Api::V1::NotificationEndpointsController` full | cookie/bearer | all actions: `api:write` | none | scoped to caller's own endpoints |
| `Api::V1::OrganizationsController` #index/#show | cookie/bearer | none | none | `current_organization` only |
| `Api::V1::OrganizationsController` #create | none (pre-auth) | n/a | n/a | creates new org for the locked user |
| `Api::V1::PoliciesController` full | cookie/bearer | write actions: `api:write` | `owner`/`admin` on create/update/destroy/upload_velato | `current_organization.policies` |
| `Api::V1::SearchController` #show | cookie/bearer | none | none | forces `tenant_id` filter in OpenSearch query |
| `Api::V1::SessionsController` #index/#destroy | cookie/bearer | `index`: `api:read` | none | caller's own tokens only |
| `Api::V1::SignupsController` #create | none (pre-auth) | n/a | n/a | none (pre-tenant), beta-code gated |
| `Api::V1::SourcesController` full | cookie/bearer | write actions: `api:write` | none | `current_organization.sources` |
| `Api::V1::SupportTicketsController` full | cookie/bearer | none | `update`: `owner`/`admin` | `current_organization.support_tickets` |
| `Api::V1::UsageLimitsController` #show/#update | cookie/bearer | none | `owner`/`admin` | `current_organization.effective_usage_limit` |
| `Api::V1::WatchlistsController` full | cookie/bearer | write actions: `api:write` | none | `current_organization.watchlists` |
| `Api::V1::WebSessionsController` #create/#destroy | none (pre-auth) / cookie (destroy reads it) | n/a | n/a | derives org from user's memberships |
| `Internal::V1::AlertsController` #create | shared secret | n/a | n/a | `tenant_id` from event body (trusted caller only) |
| `Internal::V1::NotificationTargetsController` #create/#update | shared secret | n/a | n/a | same |
| `Internal::V1::TokensController` #show | shared secret | n/a | n/a | resolves token → org/user/scopes, **no disabled-state check** (High #3) |
| `HealthController` #show | none | n/a | n/a | no tenant context |

No internal endpoint is reachable by an ordinary authenticated user's Bearer token or cookie session — confirmed via full read of `authenticate_internal!` and `ApplicationController`'s before_action chain (internal controllers never inherit it).

## 3. Complete role/permission matrix

| Action class | owner | admin | analyst | reviewer | viewer |
|---|---|---|---|---|---|
| Read own org's resources (`api:read`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Write resources (`api:write`) — sources, watchlists, investigations, alerts, notification endpoints | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Governance requests (tenant export/deletion/source takedown)** | ✅ | ✅ | ✅ (bug) | ✅ (bug) | ❌ |
| Manage policies (create/update/destroy/upload) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage memberships (role/disable/remove) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage invitations | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage usage limits / `billing_state` | ✅ | ✅ | ❌ | ❌ | ❌ |
| Update support ticket status | ✅ | ✅ | ❌ | ❌ | ❌ |
| Own preference toggle (`/me`) | ✅ | ✅ | ✅ | ✅ | ✅ |

The "Governance requests" row marked "(bug)" is Blocker #1 — `analyst`/`reviewer` should not have this, since it's a `require_role!("owner","admin")`-tier action by the same logic already applied to policies/memberships/invitations/usage-limits.

## 4. Organization-owned resource inventory

20 models, all traceable to `Organization` (14 direct `has_many`/`has_one` with `dependent: :destroy`; `watchlist_items`/`policy_versions` cascade 2 levels through their required parent). Full per-model FK/index/cascade table is in the research archive; no model was found with an orphan-prone nullable tenant path. `OutboxEvent` is the one exception worth naming here: it has a real, FK-backed `tenant_id`, but **no `has_many :outbox_events` on `Organization` at all** — no cascade path exists, and the FK would block an org `destroy` while any `outbox_events` rows for that tenant remain (Medium, documented — see §7, currently dormant since tenant deletion is a soft operation today, not a real `Organization#destroy`).

## 5. Existing protections that are correct

- Every idempotency (`find_or_initialize_by`) pattern in the app is backed by a real DB-level unique index — no silent cross-request duplicate is possible at the storage layer anywhere, even where the graceful-rescue is missing (see §6).
- Session fixation: **fully protected**. Every authentication boundary (signup, verify, login — both modes, org-create, invitation-accept) mints a brand-new `SecureRandom.hex(24)`-derived `ApiToken` server-side; no code path ever adopts a client-supplied session/token identifier.
- Disabled-membership access is blocked on every control-plane API request (`current_user_disabled_or_suspended?`, re-read fresh from DB every call, no caching).
- Logout and explicit session-revoke (`DELETE /api/v1/sessions/:id`) both actually revoke the underlying `ApiToken` row, not just clear a client-side cookie.
- Membership *removal* (`DELETE`) already bulk-revokes all of that user's org tokens — the gap is specifically the *disable-via-update* path (Blocker #3, fixed here).
- CSRF: correctly scoped (cookie + mutating only), fail-closed on a missing Origin header, and the one existing test suite (`tenant_isolation_spec.rb`) already exercises mismatched/missing/matching Origin plus the header-auth-never-checked regression case.
- Response-shape-based enumeration is already prevented on login (3 controllers) and email verification/resend (identical response bodies/status in every case) — only *timing* leaks the difference (§6).
- Org-creation flooding: structurally impossible beyond one workspace per user (atomic lock + can't remove yourself as last owner).
- Watchlist/source/notification-endpoint flooding: `enforce_usage_limit!` applies real, non-zero default limits (10/5/5) even to organizations with no persisted `UsageLimit` row — the "missing row defaults to unlimited" hypothesis in the original brief is **disproven** by direct migration-default reading.
- Beta-access-code comparison is genuinely constant-time (`secure_compare` over SHA256 digests of both sides).
- `AlertEmailNotificationJob` (the one job accepting record IDs) already re-validates tenant match, membership-enabled, and preference-opt-in at *execution* time, not just enqueue time — this is the pattern the rest of the codebase's shared idempotency/authorization helpers should be modeled on.
- Mass assignment: no controller permits `organization_id`, `user_id`, `role` (outside the intentionally-role-gated `MembershipsController`), `scopes`, or `email_verified_at`. `billing_state` is the one confirmed exception (Blocker #7).
- Role→scope mapping has zero drift/duplication — `Membership.scopes_for` and `Membership::ROLES` are each referenced from exactly the expected call sites, nothing else computes permissions independently.

## 6. Confirmed vulnerabilities (fixed in this feature — Blocker/High)

1. **[Blocker] `GovernanceRequestsController#create` has no `require_role!` gate.** Any token with `api:write` scope — i.e. `analyst` or `reviewer`, not just `owner`/`admin` — can trigger `tenant_deletion`, `tenant_export`, or `source_takedown`. Confirms the named threat "reviewer performing write operations" on the single most destructive endpoint in the app.
2. **[Blocker] Stale token scopes on role downgrade.** `require_scope!` checks `@current_api_token.allows?(scope)` — the token's `scopes` array, fixed at issuance (`ApiToken.issue!`) — never recomputed when `Membership#role` changes. A user downgraded from `owner`/`admin` to `viewer` via `PATCH /api/v1/memberships/:id` keeps full `["*"]` write access on their existing session/token for up to 30 days or until explicit revocation. Affects every `require_scope!`-gated endpoint (most writes in the app).
3. **[High] Membership disabled via `PATCH` (not `DELETE`) never revokes the token, and the internal token-introspection endpoint never checks disabled state at all.** The control-plane API itself stays protected (re-checks `disabled_at` per-request), but `Internal::V1::TokensController#show` — consumed by the Go `realtime-gateway` service to authorize real-time SSE alert-stream connections — resolves a token to org/user/scopes without ever checking `user.disabled?`/`membership.disabled?`. A member disabled via `#update` can keep opening new SSE connections for up to 30 days.
4. **[High] Rack::Attack has no configured cache store**, silently falling back to in-process memory. In any multi-replica deployment, every pod tracks independent throttle counters — the effective limit on every single throttle rule in the app becomes `configured_limit × replica_count`.
5. **[High] No audit/log trail for any security-denial event.** 401s, 403s (role/scope/CSRF), and Rack::Attack throttle hits are completely invisible today — `AuditEvent` only ever records successful, already-authorized mutations.
6. **[High] `AlertEmailDelivery` is entirely absent from the tenant export/deletion (`GovernanceRequest`) flow.** Confirmed by direct code reading of `export_snapshot`/`apply_request!` — the most recently added org-owned model, holding per-member delivery status/error data, is invisible to both the export and the deletion action.
7. **[High] `billing_state` is client-mass-assignable** via `PATCH /api/v1/usage_limit`'s permitted params, by any org `owner`/`admin`. A suspended/past-due organization's own admin can self-set `billing_state: "active"`, bypassing `require_writable_account!`'s gate entirely.
8. **[High, bundled with #2] Login timing side-channel.** `user&.authenticate(password)` short-circuits via `&.` when the email doesn't exist, so bcrypt (a deliberately slow hash) only runs for real accounts. Response shape is already identical (protected), but timing is a measurable, code-confirmed enumeration oracle across all 3 login controllers (`web_sessions_controller.rb`, `auth_controller.rb`, `organizations_controller.rb`).

## 7. Suspected or unproven risks (documented, not fixed — Medium/Low, would materially expand scope)

- **Email-verification-resend timing side-channel** (synchronous `deliver_now` means a real unverified account is measurably slower to respond than a nonexistent/verified one). Root cause is the already-locked, `TODOS.md`-documented synchronous-mail tradeoff from a prior eng review — this feature does not silently reverse that decision. Tracked as a TODO alongside the existing async-mail item.
- **SSE stream doesn't re-check authorization mid-connection** (`services/realtime-gateway/main.go`) — a fully revoked token doesn't terminate an already-open stream, only blocks new connection attempts. Separate Go service; out of scope per "do not redesign unrelated product features."
- **5 of 8 `find_or_initialize_by` idempotency sites lack graceful `RecordNotUnique` handling** app-wide (only 3 — signups, organizations, watchlists — currently rescue it). The `GovernanceRequestsController` instance is fixed here (bundled with Blocker #1's remediation, since we're already touching that controller); the other 4 (internal alerts controller, internal notification_targets, notification_endpoints `register!`, invitations controller) are documented as a follow-up using the same shared helper once it exists.
- **`OutboxEvent` has no `Organization` association/cascade path** — dormant today since tenant "deletion" is a soft operation (no real `Organization#destroy` is ever called in production code).
- **`Outbox::Publisher` trusts `tenant_id` in the event payload with no re-validation at publish time** — lower risk than it sounds, since `OutboxEvent` rows are only ever created by trusted internal app code already scoped through `current_organization`, not client-supplied.
- **No per-account login lockout.** Deliberately **not** recommended — an attacker-triggerable lockout enables a victim-lockout DoS (repeatedly submit wrong passwords for someone else's account to lock them out), and the existing IP-based throttle already provides meaningful protection without that tradeoff.
- **Missing `config.hosts` in production** (Rails' Host-header allow-list) — no active exploit path found (nothing in the app builds URLs from `request.host`), but worth a trivial hardening addition since it's a one-line config change bundled with the other quick fixes below.
- **Cookie `Secure` flag keyed on `Rails.env.production?`**, not the app's own `SIGNALCHORD_ENV` production gate used everywhere else (CORS origin validation, internal-token strength check) — a real-but-narrow drift risk if a deployment ever sets `RAILS_ENV` differently from `SIGNALCHORD_ENV`. Bundled as a quick fix.
- **`midi_data` vs `midi_base64` parameter-filter mismatch** — `config.filter_parameters` lists `midi_data`, but the actual wire param key is `midi_base64` (up to 128KB of MIDI binary), so it's never filtered from Rails' parameter logs in production. Bundled as a quick fix (one-word change).
- **Rack::Attack's default `throttled_responder` leaks the exact configured limit and reset time** via `RateLimit-Limit`/`RateLimit-Reset` headers, letting an attacker calibrate a request rate just under the threshold. Bundled as a quick fix (custom responder).
- **Broken `belongs_to :accepted_by` in `invitation.rb`** (column-name mismatch vs. the actual `accepted_by_user_id` column) — confirmed dead code, zero call sites anywhere in `app/`/`spec/`. Documented only, not fixed (touching unused code is out of scope).

## 8. Missing test coverage

`entities`, `investigations`, `memberships`, `notification_endpoints` (public controller), `policies`, `search`, `sources`, `usage_limits` have no dedicated request-spec file at all today — their only tenant-isolation coverage is a generic read/patch-by-guessed-id loop embedded in `tenant_isolation_spec.rb`. `Internal::V1::TokensController` has **zero** test coverage of any kind. Per the brief's explicit preference for "systematic shared authorization helpers and test matrices over scattered one-off patches," this feature builds one shared RSpec tenant-isolation matrix (read-by-id 404s cross-tenant + no leak, write-by-id 404s + no mutation cross-tenant, list never leaks cross-tenant rows) and includes it once per resource controller — see §13.

## 9. Missing rate limits

`invitations/accept` mints a session from a client-supplied token exactly like login/signup, yet has no dedicated throttle — only the generic 600/min catch-all. This feature adds one dedicated throttle rule for it, matching its sibling auth endpoints. Watchlist creation, notification-endpoint create, alert update, `/me` preference toggle, and search remain on the generic catch-all only — confirmed lower urgency (ordinary authenticated CRUD, no pre-auth abuse surface), documented as available future hardening rather than added now.

## 10. Required code changes

**`apps/control-plane/app/controllers/application_controller.rb`**
- Replace `require_scope!`'s token-snapshot check with a live-role-derived check:
  ```ruby
  def require_scope!(scope)
    raise Forbidden unless allowed_scopes.include?(scope) || allowed_scopes.include?("*")
  end

  def allowed_scopes
    # User-bound tokens: derive from the LIVE membership role, not the token's
    # issuance-time scopes snapshot (Blocker #2) — a role downgrade takes
    # effect on the very next request, matching how require_role! already
    # re-reads the live role. Tokens with no bound user (ApiToken.user is
    # optional) have no membership/role to consult, so fall back to the
    # token's own stored scopes for that case only.
    current_membership ? Membership.scopes_for(current_membership.role) : @current_api_token.scopes
  end
  ```
- Add a shared security-denial logger, called from every existing denial path (`render_error`, the `rescue_from Forbidden` handler, `verify_same_origin!`'s forbidden branch): a structured `Rails.logger.warn` (not an `AuditEvent` row — see §6/decision log) with `event:`, `path:`, `ip:`, `request_id:`, and `org_id:`/`user_id:` only when resolvable (many denials, like an invalid token, have no org/user context yet).

**`apps/control-plane/app/controllers/api/v1/governance_requests_controller.rb`**
- Add `before_action -> { require_role!("owner", "admin") }, only: :create` (Blocker #1), matching the exact convention already used by `PoliciesController`/`MembershipsController`/`InvitationsController`/`UsageLimitsController`.
- Add `rescue_from ActiveRecord::RecordNotUnique` (matching `WatchlistsController`'s existing pattern) to close the unrescued idempotency race on this controller specifically (§7).
- Extend `export_snapshot` to include `alert_email_deliveries` and extend `apply_request!`'s `tenant_deletion` branch to also soft-suppress/anonymize `AlertEmailDelivery` rows for the org (exact shape mirrors the existing `alerts.update_all(suppressed: true, ...)` pattern).

**`apps/control-plane/app/controllers/api/v1/memberships_controller.rb`**
- `#update`: when `disabled_at` transitions from unset to set, also revoke that user's active tokens (reuse the exact `api_tokens.where(user_id:).active.update_all(revoked_at: Time.current, ...)` call already present in `#destroy`) — closes Blocker #3 at the source.

**`apps/control-plane/app/controllers/internal/v1/tokens_controller.rb`**
- Defense-in-depth: also reject (in the response, e.g. `active: false` or a 200 with a `disabled: true` flag the caller must honor — exact shape decided during implementation to match how `realtime-gateway` consumes this response) when the resolved user/membership is disabled, so any current or future internal consumer beyond `realtime-gateway` is protected even if that service's own re-check is imperfect.

**`apps/control-plane/app/controllers/api/v1/usage_limits_controller.rb`**
- Remove `:billing_state` from the permitted params list (Blocker #7). No billing logic added or changed — this is a mass-assignment fix only.

**`apps/control-plane/app/controllers/api/v1/web_sessions_controller.rb`, `sessions_controller.rb`... wait, `auth_controller.rb`, `organizations_controller.rb`**
- Add a shared `authenticate_with_dummy_timing` (or similar) helper: when `user` is nil, run `BCrypt::Password.create("dummy")` (or equivalent constant-cost work) before returning the same `invalid_credentials` response, so response timing no longer correlates with account existence (Blocker #8).

**`apps/control-plane/config/initializers/rack_attack.rb`**
- Wire `Rack::Attack.cache.store = ActiveSupport::Cache::RedisCacheStore.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0"))` (Blocker #4) — reuses the already-present `redis` gem and `REDIS_URL` env var (already wired for Sidekiq), no new infra.
- Add `throttle("api/invitations_accept/ip", ...)` matching the shape of the existing `api/organizations_create/ip` rule (§9).
- Add a custom `Rack::Attack.throttled_responder` that omits `RateLimit-Limit`/`RateLimit-Reset` headers (§7 quick fix).

**`apps/control-plane/config/environments/production.rb`**
- Set `config.hosts` to the real production host(s) (§7 quick fix).

**`apps/control-plane/app/controllers/concerns/cookie_session.rb`**
- Change the `Secure` flag condition from `Rails.env.production?` to the same `SIGNALCHORD_ENV`-based check `ProductionConfig` already uses elsewhere, closing the drift (§7 quick fix).

**`apps/control-plane/config/application.rb`**
- Fix `filter_parameters`: replace/add `midi_base64` alongside (or instead of) `midi_data` (§7 quick fix).

## 11. Required database or constraint changes

None required to be additive-only beyond what's already correct — every uniqueness/FK constraint audited in §4/§5 is already appropriately scoped. No migration is needed for the code changes in §10 (all are application-layer: controller gates, a config store wire-up, a permitted-params removal). The one schema-adjacent item — `AlertEmailDelivery` inclusion in governance export/deletion — needs no new column, just new query code in the controller.

## 12. Required logging or observability changes

New structured security-denial log line (see §10's `application_controller.rb` change), emitted at every existing denial point: `authenticate_api_token!`'s 401/403 branches, `verify_same_origin!`'s forbidden branch, the `rescue_from Forbidden` handler (covers `require_scope!`/`require_role!`/`enforce_usage_limit!`/last-owner-protection raises), and a new subscriber on Rack::Attack's `ActiveSupport::Notifications` `"throttle.rack_attack"`/`"blocklist.rack_attach"` events (currently entirely unobserved — confirmed no subscriber exists anywhere). Shape: `{event: "security_denial", reason:, path:, method:, ip:, request_id:, org_id: (if resolvable), user_id: (if resolvable)}`.

## 13. Required security tests

- **Shared tenant-isolation matrix** (new `spec/support/tenant_isolation_examples.rb` or similar): parameterized `shared_examples` covering read-by-id (404, no cross-tenant leak in body), write-by-id (404, no mutation), and list-scoping (never includes another org's rows). Included once for each of: `entities`, `investigations`, `memberships`, `notification_endpoints`, `policies`, `search`, `sources`, `usage_limits`.
- New `spec/requests/internal_tokens_spec.rb` — currently zero coverage; cover valid/invalid internal-token auth, and (once §10's fix lands) the disabled-user/membership rejection case.
- `governance_requests_spec.rb`: add a test that a `reviewer`/`analyst`-scoped token gets 403 on `POST /api/v1/governance_requests` (regression test for Blocker #1); add a `RecordNotUnique`-race test matching `watchlists_controller`'s existing style; add an assertion that `tenant_export`/`tenant_deletion` now cover `AlertEmailDelivery`.
- `memberships_spec.rb` (new, or extend `product_operations_spec.rb`): a membership disabled via `PATCH` (not `DELETE`) results in that user's existing token becoming immediately `revoked_at`-set (Blocker #3 regression test), and — separately — a role downgrade via `PATCH` immediately changes what `require_scope!`-gated endpoints the existing token can reach (Blocker #2 regression test, e.g. downgrade owner→viewer then attempt a watchlist write with the pre-existing token, expect 403).
- `usage_limits_spec.rb` (new or extend `product_operations_spec.rb`): `billing_state` is rejected/ignored when submitted in the update params (Blocker #7 regression test).
- 3 login controllers: a timing-insensitive regression test isn't practical in CI (flaky by nature), so instead assert the *code path* runs a dummy comparison — e.g. a test double/spy confirming `BCrypt::Password.create` (or equivalent) is invoked even when `user` is nil (Blocker #8 regression test, structural not timing-based).
- `rack_attack`-related: a request spec confirming the invitations/accept throttle triggers at its configured limit (matching the existing style for other throttled endpoints); a spec confirming the custom `throttled_responder` omits the `RateLimit-*` headers.
- A spec asserting the security-denial log line fires (using an `RSpec::Mocks` expectation on `Rails.logger` or a custom `ActiveSupport::Notifications` subscriber assertion) for at least one representative case of each: invalid token, CSRF rejection, role/scope denial.

## 14. Recommended phased implementation plan

1. **Phase 1 — authorization core**: `require_scope!` live-role fix (Blocker #2), `GovernanceRequestsController` role gate + idempotency rescue (Blocker #1 + §7 item), `MembershipsController#update` token revocation on disable (Blocker #3), `Internal::V1::TokensController` disabled-state check (Blocker #3 continued), `UsageLimitsController` `billing_state` removal (Blocker #7). Tests alongside each.
2. **Phase 2 — abuse controls**: Rack::Attack Redis store wire-up (Blocker #4), invitations/accept throttle, custom throttled_responder, login timing fix (Blocker #8) across all 3 controllers. Tests alongside.
3. **Phase 3 — observability**: shared security-denial logger + Rack::Attack notification subscriber, wired into every existing denial point. Tests alongside.
4. **Phase 4 — data governance**: `AlertEmailDelivery` added to `GovernanceRequest` export/deletion (High #6). Tests alongside.
5. **Phase 5 — quick hardening bundle**: `config.hosts`, cookie `Secure`-flag env-check fix, `midi_data`/`midi_base64` filter-parameter fix — all small, independent, bundled together.
6. **Phase 6 — test matrix**: shared tenant-isolation `shared_examples`, applied to the 8 under-covered controllers; new `internal_tokens_spec.rb`.
7. **Phase 7 — verification**: full local suite (`pnpm typecheck/lint/test/build` where applicable — this is backend-only, so Rails specs verified via CI, no Ruby in this sandbox), push, PR.

## 15. Files likely to change

| File | Change |
|---|---|
| `apps/control-plane/app/controllers/application_controller.rb` | `require_scope!`/`allowed_scopes` live-role fix; shared security-denial logger |
| `apps/control-plane/app/controllers/api/v1/governance_requests_controller.rb` | `require_role!` gate, `RecordNotUnique` rescue, export/deletion coverage for `AlertEmailDelivery` |
| `apps/control-plane/app/controllers/api/v1/memberships_controller.rb` | Token revocation on disable-via-update |
| `apps/control-plane/app/controllers/internal/v1/tokens_controller.rb` | Disabled-state check |
| `apps/control-plane/app/controllers/api/v1/usage_limits_controller.rb` | Remove `billing_state` from permitted params |
| `apps/control-plane/app/controllers/api/v1/web_sessions_controller.rb`, `auth_controller.rb`, `organizations_controller.rb` | Dummy-timing login fix |
| `apps/control-plane/config/initializers/rack_attack.rb` | Redis store, invitations/accept throttle, custom responder |
| `apps/control-plane/config/environments/production.rb` | `config.hosts` |
| `apps/control-plane/app/controllers/concerns/cookie_session.rb` | Secure-flag env-check fix |
| `apps/control-plane/config/application.rb` | `midi_base64` filter fix |
| `apps/control-plane/spec/support/tenant_isolation_examples.rb` | New shared matrix |
| `apps/control-plane/spec/requests/internal_tokens_spec.rb` | New |
| `apps/control-plane/spec/requests/{entities,investigations,memberships,notification_endpoints,policies,search,sources,usage_limits}_spec.rb` | New or extended, including the shared matrix |
| `apps/control-plane/spec/requests/governance_requests_spec.rb`, `product_operations_spec.rb` | Extended regression tests |
| `TODOS.md` | New entries: broader governance-export completeness (all 20 models), email-verification-resend timing side-channel, SSE mid-stream re-auth, remaining 4 `RecordNotUnique` sites, broader rate-limit coverage |

## 16. Acceptance criteria

1. A token with `analyst`/`reviewer` scope receives 403 on `POST /api/v1/governance_requests`.
2. A user downgraded from `owner`/`admin` to any lower role via `PATCH /api/v1/memberships/:id` immediately loses `api:write`-gated access on their pre-existing token/session — verified without requiring re-login.
3. A membership disabled via `PATCH /api/v1/memberships/:id` (not `DELETE`) results in that user's tokens being `revoked_at`-set immediately, and `Internal::V1::TokensController` independently rejects/flags a disabled user/membership.
4. `PATCH /api/v1/usage_limit` ignores or rejects a client-supplied `billing_state`.
5. Rack::Attack's cache store is Redis-backed; throttle counts are consistent across multiple app processes sharing the same Redis instance (verified by a spec that hits the limit via two separate `Rack::Attack.cache` instances pointed at the same store).
6. `POST /api/v1/invitations/accept` is throttled at a defined per-IP limit within a defined period.
7. A nonexistent-email login attempt and a real-email-wrong-password attempt both execute a bcrypt-equivalent comparison (verified structurally, not by timing measurement).
8. A representative denial of each type (invalid token, CSRF rejection, role/scope denial) produces a structured log line.
9. `GovernanceRequest` `tenant_export`/`tenant_deletion` responses/effects include `AlertEmailDelivery` rows for the requesting organization.
10. The 8 previously-uncovered controllers each have a passing tenant-isolation test via the shared matrix; `Internal::V1::TokensController` has passing request specs.
11. No existing test regresses; all new tests pass in CI (no Ruby/Docker in this sandbox — verified via CI, not locally).
12. RBAC, tenant isolation, CSRF, cookie security, and all existing idempotency guarantees are preserved or strengthened — never weakened — for both cookie-session and bearer-token use cases.

## 17. Recommended next gstack command

`/plan-eng-review` — this spec changes a foundational, app-wide authorization primitive (`require_scope!`'s live-role derivation touches nearly every write endpoint), closes a genuine tenant-destructive-action authorization gap, and introduces a new cross-cutting logging concern — exactly the kind of architecture-level change that benefits from a dedicated engineering review pass (including an outside-voice second opinion) before implementation starts, matching the pattern used for both prior features.

## 18. Eng review decisions (locks §10/§15, read alongside them)

The following decisions were made during `/plan-eng-review` (2026-07-23) and take precedence over the corresponding §10 prose where they add specificity:

- **Internal::V1::TokensController disabled-state fix (Blocker #3, continued):** ships as a **non-2xx status** (e.g. 403), not a `disabled: true` flag on a 200. Verified against the actual Go consumer (`services/realtime-gateway/main.go:206-220`): it already treats any non-200 as a hard failure and its `tokenIntrospection` struct silently drops unknown JSON fields, so a flag-on-200 shape would ship a fix that doesn't fix anything. Zero changes to `main.go` required.
- **Dummy-timing helper (Blocker #8):** new `app/controllers/concerns/dummy_timing_authentication.rb` (`ActiveSupport::Concern`), mirroring the existing `CookieSession` pattern, included by all 3 login controllers. Not a duplicated private method — `WebSessionsController` and `AuthController` don't inherit `ApplicationController`, so a shared method can't live there.
- **Token-revocation DRY (Blocker #3):** extract a private `revoke_active_tokens!` in `memberships_controller.rb`, called from both `#update` and `#destroy`, instead of pasting the same `.active.update_all(revoked_at: ...)` line into `#update` as originally drafted.
- **Disabled-check DRY (new, surfaced by review):** the "is this token's user/membership disabled" check gets extracted onto the model as `ApiToken#user_or_membership_disabled?`. `ApplicationController#current_user_disabled_or_suspended?` delegates to it; `Internal::V1::TokensController` calls the same method for its Blocker #3 fix, instead of reimplementing the same 3-line check a second time.
- **Quick-hardening-bundle tests (§7/§10):** all 3 (`config.hosts`, cookie Secure-flag env-check, `midi_base64` filter fix) get a regression test each — the original draft shipped these untested.
- **Rack::Attack Redis fail-open (Blocker #4):** explicitly confirmed and tested (not left as an undocumented library default) — a Redis connection error must not 503 the whole API, since the `api/ip` catch-all throttle fires on every request under `/api/*`.

6 new TODOS.md entries added (see `## Tenant Security Hardening` section): email-verification-resend timing side-channel, SSE mid-stream re-auth, remaining 4 unrescued `RecordNotUnique` sites, full 20-model governance export/deletion coverage, broader rate-limit coverage, and a typed disabled-signal follow-up for `realtime-gateway`.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 6 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run (backend-only feature) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

**CROSS-MODEL:** Outside voice unavailable this run — Codex CLI auth failed (401, consistent all session), and the Claude-subagent fallback hit an account spend-limit error (non-retryable, non-transient). Findings above are single-model (Claude), verified directly against source (application code + the Go consumer), not inferred.
**VERDICT:** ENG CLEARED — ready to implement. Outside-voice cross-check did not run; re-running it before merge is optional, not required, given every finding here was independently verified against real code rather than pattern-matched.

NO UNRESOLVED DECISIONS
