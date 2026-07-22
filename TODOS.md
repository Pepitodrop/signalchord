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
