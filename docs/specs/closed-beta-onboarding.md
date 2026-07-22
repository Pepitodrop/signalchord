---
status: approved (spec + eng review complete)
branch: feature/closed-beta-onboarding
reviewed: 2026-07-22 (/spec, /plan-eng-review)
---

# Closed-Beta Onboarding: Signup → Verify Email → Login → Create Workspace → Owner → First-Watchlist

## Context

SignalChord's control plane (`apps/control-plane`, Rails 8 API) already has a complete multi-tenant data model — `User`, `Organization` (the "workspace"), `Membership` with a 5-role set (`owner/admin/analyst/reviewer/viewer`), and a working invite-acceptance flow. What's missing is any way for a new person to get in without someone already inside an org inviting them. For closed beta, self-serve signup gated by a shared access code, with real email verification, ending with the user owning a brand-new workspace and landing on a real first-watchlist step — without touching billing, MFA, per-user invitations, or the watchlist feature itself.

## Current State (verified 2026-07-22)

| Capability | Status |
|---|---|
| Self-serve signup | Missing — no `POST /users`/`POST /signup` anywhere |
| Email verification | Missing — zero infrastructure |
| User/Org/Membership models | Exists, unchanged |
| Owner/admin/member roles | Exists, richer than asked (5 roles) |
| Tenant isolation | Exists at API layer, tested; broken for a brand-new user because `ApiToken.organization_id` is `NOT NULL` |
| First-watchlist onboarding UI | Missing — no router in `apps/web` at all |
| Watchlist creation API | Exists, reused as-is — `POST /api/v1/watchlists` |
| Web session storage | Anti-pattern in place — bearer token in `localStorage` |
| Mobile session storage | Correct, out of scope — `expo-secure-store` |
| Email infrastructure | Zero |
| Background job runner | Gemfile/config only — `sidekiq` configured as ActiveJob adapter but no worker process runs anywhere |
| CORS | Exists, needs `credentials: true` |
| CSRF protection | None — expected, no cookie auth today |
| Rate limiting | Exists, pattern to extend |
| Test conventions | RSpec (control-plane), Vitest (web); no `spec/models/` dir yet; no e2e framework at all |

## Decisions (final, post /spec + /plan-eng-review)

1. **Web auth**: httpOnly, Secure, encrypted cookie holding the same opaque `ApiToken` value. Mobile's bearer+header flow is untouched.
2. **Closed-beta gate**: one server-side `BETA_ACCESS_CODE` env var, constant-time compared, required only at signup. Never shipped to the frontend bundle, never logged.
3. **Email**: ActionMailer + SMTP (vendor-agnostic), Mailpit for local dev. Synchronous delivery (`.deliver_now`) — deliberate, since no Sidekiq worker exists. If the mailer raises, the User row still exists and signup returns 201 (logged, not swallowed); resend is the recovery path.
4. **Verification tokens**: Rails 8 built-in `generates_token_for` — **no new table**. `User.generates_token_for(:email_verification, expires_in: 24.hours) { [email_verified_at, verification_email_sent_at] }`. Single-use falls out for free: once `email_verified_at` changes, the token's embedded scope digest no longer matches, so replay fails automatically.
5. **No pending/intermediate session of any kind.** A verified user with zero orgs who "logs in" gets NO cookie — a stateless `{status: "workspace_required"}` response. The frontend holds the just-typed email+password in memory (same SPA, no reload) and bundles them into `POST /api/v1/organizations`, which re-validates credentials fresh before creating anything. Only after the org exists does a real cookie get set. *(Reconfirmed after outside-voice challenge in eng review — kept as decided.)*
6. **No `react-router-dom`.** Hand-rolled `pathname` matching over ~5 fixed paths, matching the existing `View`-union style.
7. **Onboarding state** is derived, computed server-side in one place, never a stored "completed" flag:
   ```
   no email_verified_at                          → verification_required
   verified, zero ENABLED Memberships             → workspace_required
   Membership, zero Watchlists                    → first_watchlist_required
   Membership + ≥1 Watchlist                      → complete
   ```
8. **`Membership.scopes_for(role)`** is one shared class method — fixes an existing silent disagreement between `AuthController` and `InvitationsController` (owner/admin scope mapping) as a side effect — used by `AuthController`, `InvitationsController`, and the new `OrganizationsController#create`.
9. **Migration is purely additive**: `users.email_verified_at` (datetime, nullable) + `users.verification_email_sent_at` (datetime, nullable). No new tables.
10. `POST /api/v1/organizations` gets its own rack-attack throttle (mirrors `auth/session`'s shape) since it's now a full credential-validation endpoint.
11. `POST /api/v1/organizations`: slug auto-derived from the typed workspace name, auto-suffixed (`-2`, `-3`, ...) on collision — never a raw validation error on a field the user never saw. Rejects (422) if the caller already has ≥1 enabled Membership.
12. New endpoints: `POST /api/v1/signup`, `POST /api/v1/email_verifications`, `POST /api/v1/email_verifications/resend` (identical response body regardless of whether the email exists/is already verified), `POST`+`DELETE /api/v1/auth/web_session`, `POST /api/v1/organizations` (extends existing controller), `GET /api/v1/me`.
13. Frontend: `SignupPage`, `VerifyEmailPage`, `LoginPage`, `OnboardingWorkspacePage`, `OnboardingWatchlistPage` (reuses the existing `POST /api/v1/watchlists` endpoint, unchanged), `ProtectedRoute`. Only `main.tsx`'s top-level session/login wiring changes — `Policies`/`Watchlists`/`Alerts`/`Sources`/`Entities`/`VelatoShowcase`/`MerzatoStudio`/`MerzSpeech*` untouched. Live Lab (`lab.html`/`lab.js`) untouched, including its own separate `localStorage` check — accepted, explicit exclusion.

## 13 Blocking Changes from /plan-eng-review (all mandatory, all resolved)

| # | Change | File(s) |
|---|---|---|
| 1 | Drop `PendingSession` — no session until workspace exists | (removed from design) |
| 2 | Drop custom `EmailVerification` table — use `generates_token_for` | `app/models/user.rb` |
| 3 | Drop `react-router-dom` — hand-rolled pathname matching | `apps/web/src/main.tsx` |
| 4 | Add global `verify_same_origin!` before_action (CSRF) | `app/controllers/application_controller.rb` |
| 5 | Add rack-attack throttle on `organizations#create` | `config/initializers/rack_attack.rb` |
| 6 | Onboarding-state derivation uses `memberships.enabled`, not raw existence | new `Api::V1::MeController` |
| 7 | Extract `Membership.scopes_for(role)` into one shared method | `app/models/membership.rb`, `auth_controller.rb`, `invitations_controller.rb` |
| 8 | Mailer exceptions rescued — signup still returns 201, logged | `app/controllers/api/v1/signups_controller.rb` |
| 9 | Slug auto-suffix on collision; block a second workspace via this endpoint | `app/controllers/api/v1/organizations_controller.rb` |
| 10 | `GET /api/v1/me` computes state server-side using `.exists?` | new `Api::V1::MeController` |
| 11 | **`InvitationsController#accept` sets `email_verified_at`** (confirmed bug fix) | `app/controllers/api/v1/invitations_controller.rb` |
| 12 | Explicit SMTP `open_timeout`/`read_timeout` | `config/environments/{development,production}.rb` |
| 13 | `rescue_from ActiveRecord::RecordNotUnique` in `SignupsController`, mapped to the same 422 duplicate-email response as `RecordInvalid` | `app/controllers/api/v1/signups_controller.rb` |

## Environment Variables (new)

| Var | Purpose | Default |
|---|---|---|
| `BETA_ACCESS_CODE` | shared closed-beta gate | *(required in prod, no default)* |
| `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` | verification link lifetime | `24` |
| `SESSION_COOKIE_NAME` | web session cookie name | `sc_session` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_AUTHENTICATION`, `SMTP_STARTTLS` | vendor-agnostic mail delivery | `mailpit`/`1025`/unset/unset/`plain`/`false` in dev |
| `SMTP_OPEN_TIMEOUT`, `SMTP_READ_TIMEOUT` | bound SMTP round-trip so a hung provider can't exhaust Puma's thread pool | `5` (seconds) each |
| `MAILER_FROM_ADDRESS` | From: header | `beta@signalchord.example` |
| `PUBLIC_WEB_URL` | base URL for the verification link | `http://localhost:5173` |

## Approved 6-Phase Implementation Plan

1. **Backend foundation** — migration, `Membership.scopes_for` consolidation, invitation-path verification fix. Tests written alongside.
2. **Backend auth + signup surface** — signup, verification, resend, web session, organization creation, dual-mode auth chokepoint, CSRF check, mailer (with timeouts), rate limits, `RecordNotUnique` handling. Tests written alongside.
3. **Backend onboarding-state endpoint** — `GET /api/v1/me`. Tests written alongside.
4. **Mailpit + environment infrastructure** — docker-compose, env vars, `.env.example` fix.
5. **Frontend onboarding flow** — hand-rolled routing, 5 pages, `ProtectedRoute`, api-client methods.
6. **Test hardening + Playwright e2e** — full coverage pass, introduce Playwright, 3 e2e flows (happy path, expired-link recovery, wrong-beta-code rejection).

## Out of Scope

Billing, MFA, per-user invitations (existing flow untouched beyond the one-line verification fix), the watchlist feature itself beyond creating one empty row, org-picker UI for >1 membership (TODOS.md), async/Sidekiq mail delivery (TODOS.md), CSP header introduction, Live Lab's own localStorage pattern, beta-code check on invitation acceptance (confirmed intentional — invitation is its own admission path), scoped "org:create" session token (outside-voice alternative to decision 5 — considered and rejected).

## Acceptance Criteria

See `/plan-eng-review` test coverage trace (47 branches) — condensed:
1. Signup respects the beta code gate and returns 201/401/422 correctly, including for concurrent duplicate signups (422, not 500).
2. Verification is single-use and expiring; replay after success fails.
3. Login blocks unverified users; issues no cookie for 0-membership users; issues a real cookie for ≥1-membership users.
4. Organization creation re-validates credentials fresh, auto-suffixes slug collisions, blocks a second workspace via this endpoint, and is rate-limited.
5. `GET /api/v1/me` correctly reports all 4 onboarding states, including for invited (non-self-serve) users.
6. No auth token appears in any JS-readable storage.
7. Cross-site mutating requests to cookie-authenticated endpoints are rejected.
8. Cross-tenant isolation holds for every new and touched endpoint (existing `tenant_isolation_spec.rb`, extended).
9. Existing mobile bearer-token flow and existing invited-member flow are provably unchanged (regression specs).
10. `pnpm typecheck`, `pnpm test`, `pnpm build`, `bundle exec rspec`, and the new Playwright suite all pass; Velato/Merzato/Live Lab/Policy Studio show zero change in test outcome.
