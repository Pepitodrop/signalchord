# TODOS

## Onboarding

### Async mail delivery (Sidekiq worker)

**What:** Stand up an actual Sidekiq worker process so verification/resend emails can move from synchronous `.deliver_now` to `.deliver_later`.

**Why:** `config.active_job.queue_adapter` is already `:sidekiq` and the gem is in the Gemfile, but no worker process exists in any docker-compose file today. The closed-beta onboarding spec deliberately uses synchronous delivery to avoid standing up new infra at low volume, but that means every signup/resend request blocks on an SMTP round-trip.

**Context:** Synchronous delivery was a deliberate, reviewed tradeoff (see `/plan-eng-review` on the closed-beta onboarding spec, 2026-07-22), not an oversight. Revisit only if signup volume or SMTP latency actually becomes a problem.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Org-picker UI for users with multiple memberships

**What:** A real "choose which workspace" screen for a user who belongs to ≥2 organizations, instead of `WebSessionsController` silently picking the most recently created active Membership.

**Why:** Unreachable through the closed-beta signup path alone (it only ever creates one org), but becomes reachable the moment an existing Invitation (untouched, existing flow) adds a second org to a user who also self-signed-up.

**Context:** Currently a documented, deliberate limitation (both in the original `/spec` and the `/plan-eng-review` that followed, 2026-07-22) — the fallback (most-recent active membership) is safe, just not a full experience. Requires a "switch organization" concept that doesn't exist anywhere in this app today.

**Effort:** M
**Priority:** P3
**Depends on:** None

## Tenant Security Hardening

### Email-verification-resend timing side-channel

**What:** Synchronous `deliver_now` in `User#send_verification_email!` makes a real unverified account measurably slower to respond to a resend request than a nonexistent/verified one, leaking account existence via timing.

**Why:** Same class of bug as the login timing fix (`tenant-security-hardening`, Blocker #8), but the root cause is the already-locked synchronous-mail tradeoff (see "Async mail delivery" above) — a local patch here can't fix it, only finishing the async-mail migration can.

**Context:** Confirmed by direct code reading during the `tenant-security-hardening` spec/eng-review (2026-07-22). Revisit together with "Async mail delivery (Sidekiq worker)" above — fixing that migration closes this gap as a side effect.

**Effort:** M
**Priority:** P3
**Depends on:** Async mail delivery (Sidekiq worker)

### SSE stream doesn't re-check authorization mid-connection

**What:** `services/realtime-gateway/main.go` authorizes an SSE connection once at open time via `internal/v1/token`; a token revoked or membership disabled after that point doesn't terminate an already-open stream, only blocks new connection attempts.

**Why:** The `tenant-security-hardening` feature fixes new-connection authorization (disabled users get rejected on the next connect), but an existing open stream for a just-disabled user keeps flowing until it naturally drops or the client reconnects.

**Context:** Separate Go service, different deploy pipeline — confirmed by reading `main.go`'s subscribe loop during the `tenant-security-hardening` eng review (2026-07-22). Fixing it for real means periodic re-introspection or a revocation-push mechanism in `main.go`. Low urgency: stream windows are typically short-lived.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Remaining unrescued RecordNotUnique idempotency races

**What:** 4 of 8 `find_or_initialize_by` idempotency sites still raise a raw 500 on a genuine concurrent double-submit instead of returning the idempotent replay: the internal alerts controller, internal notification_targets controller, `notification_endpoints#register!`, and the invitations controller.

**Why:** `tenant-security-hardening` fixes a 4th site (`governance_requests_controller.rb`, bundled with its Blocker #1 fix since that controller is already being touched), following the same rescue shape already proven in `watchlists_controller.rb`. The remaining 4 are the same mechanical fix, not yet applied.

**Context:** Fix shape: re-fetch by idempotency key inside a `rescue_from ActiveRecord::RecordNotUnique`, return the existing record instead of a raw 500. None of the 4 remaining sites are ordinary-user-facing write races (mostly internal/background paths), so real-world exposure is low but not zero (e.g. a flaky mobile client double-submitting notification-endpoint registration).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Governance export/deletion doesn't cover all 20 org-owned models

**What:** `tenant-security-hardening` adds `AlertEmailDelivery` to the tenant export/deletion flow (High #6), but `export_snapshot`/`apply_request!` still omit most org-owned models — e.g. `notification_endpoints`, `notification_deliveries`, `support_tickets`, `invitations`, `memberships`, `audit_events`, `usage_limit`.

**Why:** `AlertEmailDelivery` was prioritized as the most recently added, highest-risk-of-oversight model. The others are older and were explicitly scoped out of this security PR to avoid re-litigating the entire export/deletion surface (a real GDPR/CCPA-style "export everything, delete everything" guarantee needs all 20 models, not 6).

**Context:** Decision confirmed twice — once during `/spec` (AlertEmailDelivery-only scope), once during `/plan-eng-review` (2026-07-22) when re-raised and re-confirmed rather than expanded. Today's tenant "deletion" is a soft operation, so there's no active compliance deadline forcing this, but a real data-subject request would expose the gap immediately.

**Effort:** L
**Priority:** P3
**Depends on:** None

### Broader rate-limit coverage beyond invitations/accept

**What:** `tenant-security-hardening` adds a dedicated Rack::Attack throttle for `invitations/accept` (mints a session from a client-supplied token, like login/signup). Watchlist creation, notification-endpoint create, alert update, `/me` preference toggle, and search remain on only the generic 600/min-per-IP catch-all.

**Why:** Those 5 are ordinary authenticated CRUD with no pre-auth abuse surface (unlike `invitations/accept`), confirmed lower urgency during the spec's research pass — not unprotected, just less tightly bounded.

**Context:** If usage patterns ever show one of these being hammered (e.g. search cost, or watchlist-limit-adjacent flooding), a dedicated throttle is the same shape already proven for `invitations/accept` and the other auth endpoints in `rack_attack.rb`.

**Effort:** S
**Priority:** P4
**Depends on:** None

### Typed disabled signal for realtime-gateway token introspection

**What:** `Internal::V1::TokensController` (fixed in `tenant-security-hardening`, Blocker #3) returns a non-2xx status when the resolved user/membership is disabled, which `services/realtime-gateway/main.go` already treats as a hard failure with zero Go-side changes needed. That "non-200 = deny" behavior is current behavior, not a documented contract.

**Why:** A future refactor of either side that assumes "200 means the body has the real answer, check a field" instead of relying on the status code could silently reintroduce the disabled-user SSE-authorization gap this PR closes.

**Context:** Surfaced during the `tenant-security-hardening` eng review (2026-07-22) as a defense-in-depth follow-up, not a current gap — the shipped fix is fully correct as-is. Worth doing when someone is already touching `main.go` for other reasons: add an explicit `disabled` field check in addition to the status code.

**Effort:** S
**Priority:** P4
**Depends on:** None
