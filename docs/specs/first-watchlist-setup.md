---
status: approved (spec complete, implementing)
branch: feature/first-watchlist-setup
base: main @ 7e9bf15 (PR #91 merged)
---

# First-Use Watchlist and Source Setup

## Journey

Onboarding complete → name first watchlist → define the monitored subject/entity → choose a supported "source configuration" → create the watchlist → see a real first-analysis result → land on the normal Watchlists dashboard view with the new watchlist visible.

## 1. What already exists

| Capability | Status | Evidence |
|---|---|---|
| `Watchlist`/`WatchlistItem` models | Exists, unchanged | `app/models/watchlist.rb`, `watchlist_item.rb` — `target_kind` enum (`entity`/`topic`/`search`), `target_stable_id`, `relevance_weight` |
| `POST/GET/PATCH/DELETE /api/v1/watchlists` | Exists, tenant-scoped, RBAC-gated | `watchlists_controller.rb` — `require_scope!("api:write")`, `require_writable_account!`, `enforce_usage_limit!(:watchlists)` |
| Real synchronous lookup endpoints | Exists, genuinely operational | `GET /api/v1/search?q=` (tenant-scoped OpenSearch, `search_controller.rb`), `GET /api/v1/entities/:id` (live Neo4j proxy via graph-query, `entities_controller.rb`) |
| Onboarding-state derivation | Exists, needs strengthening | `me_controller.rb#onboarding_state_for` — currently `unless current_organization.watchlists.exists?`, doesn't check for items |
| Onboarding placeholder page | Exists, confirmed placeholder | `apps/web/src/routes/OnboardingWatchlistPage.tsx` — name-only form, `createWatchlist({name, items: []})` |
| Idempotency pattern | Exists, proven, reusable | `GovernanceRequest` — `Idempotency-Key` header/param, `find_or_initialize_by` + `new_record?` guard, 201-vs-200 via `previously_new_record?` (`governance_requests_controller.rb`) |
| Dashboard Watchlists view | Exists, flat list, no selection concept | `Watchlists` component in `apps/web/src/main.tsx` |
| Tenant isolation, CSRF, cookie session | Exists, proven (106 RSpec examples) | `ApplicationController`, `CookieSession` |

## 2. What is missing

- Real onboarding form: name + `target_kind` + `target_stable_id` (currently name-only, zero items)
- Idempotency protection on `POST /api/v1/watchlists` (currently none — a double-click or retry creates two watchlists)
- Client-side duplicate-submit guard (disable button while in flight)
- Strengthened onboarding-state check requiring ≥1 real `WatchlistItem`, not just an empty `Watchlist` shell
- Synchronous, honest "first analysis" result shown right after creation
- A way to land on the Watchlists dashboard tab with the new watchlist visible (dashboard currently always defaults to Overview, has no per-item highlight/selection concept)
- Understandable field-level validation errors surfaced in the onboarding UI (currently a single generic error string)

## 3. Recommended minimum supported source type

**"Source configuration" = `WatchlistItem.target_kind`** (confirmed decision — see rationale below), not the `Source` model. All three enum values (`entity`, `topic`, `search`) are equally real and equally supported — the backend treats them identically (same validation, no per-kind special processing downstream). Recommend defaulting the onboarding form's selection to **`entity`** (matches the user's own framing: "a company, person, or technology") while still offering `topic`/`search`, rather than artificially restricting to one.

**Why not the `Source` model:** `Source` requires a full compliance-metadata block (`legal_basis`, `deletion_obligations`, `attribution`, `geography`, etc. — `source.rb`'s `REQUIRED_APPROVAL_METADATA`) before it can be `enabled`. Separately, and independently of that gate, **nothing in the ingestion pipeline reads the `sources` table at all** — `feed-collector` runs once at `dev-up` time from hardcoded environment variables, not from any `Source` row. Building "pick/register a Source" into onboarding would mean either an impossible compliance form for a brand-new user, or a form that succeeds but does nothing — the exact "mock production behavior" ruled out for this feature.

## 4. Backend changes

### `MeController#onboarding_state_for`
Smallest safe change: `unless current_organization.watchlists.exists?` → `unless current_organization.watchlists.joins(:watchlist_items).exists?`. Single indexed EXISTS-style query via JOIN, no N+1. **Regression note:** this intentionally changes behavior for orgs whose only watchlist has zero items — they now correctly resolve to `first_watchlist_required` instead of `complete`. The existing `me_spec.rb` test that creates an empty watchlist and expects `"complete"` must be updated to reflect this deliberate change, not preserved as-is.

### `WatchlistsController#create` — idempotency (backward compatible)
- New nullable `watchlists.idempotency_key` column (migration below).
- Reads key via `request.headers["Idempotency-Key"].presence || params[:idempotency_key].presence` — **optional**. No key → behavior is byte-identical to today (always creates, 201).
- Key present → `current_organization.watchlists.find_or_initialize_by(idempotency_key: key)`; all side effects (`assign_attributes`, `save!`, `replace_items`, `audit!`) run only `if record.new_record?`, wrapped in a transaction — exact structural mirror of `GovernanceRequest`. Response status: `record.previously_new_record? ? :created : :ok`.
- `rescue_from ActiveRecord::RecordNotUnique` — a genuine concurrent double-submit with the same key races past the `new_record?` check; re-fetch the now-committed record and return it as `200`, not a 500 or generic conflict. This is friendlier than the `organizations#create` slug case: retrying an identical idempotent request should transparently return the resource, not force a client-side retry loop.
- No change to `require_scope!`, `require_writable_account!`, `enforce_usage_limit!`, or the existing non-keyed code path — RBAC and tenant scoping are untouched.

### Migration (purely additive)
```ruby
class AddIdempotencyKeyToWatchlists < ActiveRecord::Migration[8.0]
  def change
    add_column :watchlists, :idempotency_key, :string
    add_index :watchlists, [:organization_id, :idempotency_key], unique: true
  end
end
```
Postgres unique indexes permit multiple `NULL` values natively (NULL ≠ NULL in a unique constraint), so existing/ordinary non-keyed creates are unaffected. Rails validation: `validates :idempotency_key, uniqueness: { scope: :organization_id }, allow_nil: true`.

## 5. Frontend changes

`OnboardingWatchlistPage.tsx` — full rewrite (currently placeholder):
1. Form: watchlist name, `target_kind` select (entity/topic/search, defaults to entity), `target_stable_id` text input with contextual label/placeholder per kind.
2. Submit button disables while in flight (duplicate-submit guard); generates one `crypto.randomUUID()` per mount, sent as `Idempotency-Key`.
3. On success, **stay on the page** and synchronously call the real lookup: `client.entity(target_stable_id)` for `entity` kind (exact stable-id match), `client.search(target_stable_id)` for `topic`/`search` (free-text match) — this is the "first analysis" step. Any failure/404/empty result is treated as a genuine, honest empty state ("nothing indexed yet — we'll keep watching"), never fabricated.
4. A "Continue to dashboard" action then hands the created watchlist's id up to `ProtectedRoute`, which re-derives onboarding state (`refresh()`) and separately tracks the id as a one-time highlight target passed into `App`.
5. `App` defaults its initial `view` to `"watchlists"` (instead of always `"overview"`) when a highlight id was passed in; `Watchlists` component receives the id, applies a highlight class + scrolls it into view on mount. Captured once via `useState` initializer (no prop-watching needed — `App` mounts once per session).

`packages/api-client/src/index.ts`: `createWatchlist(watchlist, idempotencyKey?)` — optional second param, backward compatible; existing callers (dashboard's own "Add watchlist" mini-form) unaffected.

A small pure function `chooseAnalysisLookup(kind)` (mirroring `deriveStep.ts`'s precedent for DOM-free unit testing) decides `entity` vs `search` client-call routing.

## 6. Database/migration changes

One migration (above) — purely additive, one nullable column + one unique index. No changes to `watchlist_items`, `organizations`, or any other table.

## 7. Background-processing changes

**None.** Confirmed no consumer anywhere reacts to `Watchlist`/`WatchlistItem` creation (no `OutboxEvent`, no Kafka topic, no callback). This spec does not add any — the "first analysis" is a synchronous HTTP call to already-real endpoints, not a queued job. Per the explicit constraint: if no real background pipeline exists for this, don't invent one.

## 8. Security and concurrency risks

| Risk | Mitigation |
|---|---|
| Duplicate watchlist from double-click/retry | Idempotency-Key, backed by a real unique index + `find_or_initialize_by` guard |
| Concurrent identical idempotent requests race past the pre-check | `rescue_from ActiveRecord::RecordNotUnique` → re-fetch and return 200, not 500 |
| Cross-tenant idempotency key collision | Unique index scoped `[organization_id, idempotency_key]` — same key in two different orgs never collides |
| Trusting organization id from the client | Not applicable here — `current_organization` is derived server-side from the authenticated token exactly as every other endpoint already does; nothing in this feature accepts an org id as a request param |
| RBAC bypass | None introduced — idempotency logic sits inside the existing `require_scope!`/`require_writable_account!` chain, unchanged |
| CSRF / cookie session | Untouched — `POST /api/v1/watchlists` already goes through `ApplicationController`'s `verify_same_origin!` for cookie-authenticated requests |

## SSE cookie-auth limitation

Does not affect this feature. The known limitation (dashboard's live alert stream can't carry the httpOnly cookie to the separate realtime-gateway) is orthogonal to watchlist creation, which is a plain synchronous HTTP POST/GET. Not expanding scope to touch it.

## 9. Required tests

| Layer | What |
|---|---|
| Unit (RSpec) | Updated `me_spec.rb` — empty-item watchlist → `first_watchlist_required` (not `complete`, intentional behavior change); watchlist with ≥1 item → `complete` |
| Unit (RSpec) | `Watchlist` idempotency validation (`allow_nil: true` uniqueness scoped per org) |
| Request/integration (RSpec) | `POST /api/v1/watchlists` with `Idempotency-Key`: first call 201, replay same key → 200 same record, no duplicate row; without key → unchanged 201-always behavior (regression); simulated `RecordNotUnique` race → clean 200, not 500 |
| Tenant isolation (RSpec) | Same idempotency key in two different orgs does not collide |
| Unit (Vitest) | `chooseAnalysisLookup(kind)` pure function, all 3 `target_kind` values |
| E2E (Playwright) | Extend the existing suite: after workspace creation, fill name + kind + subject, submit, see the first-analysis result (real, possibly empty), continue, land on Watchlists tab with the new watchlist visible/highlighted |

## 10. Phased implementation plan

1. **Backend**: migration, `Watchlist` idempotency validation, `WatchlistsController#create` idempotency + `RecordNotUnique` rescue, `MeController` strengthened check — with tests alongside.
2. **Frontend**: api-client `createWatchlist` idempotency param, `chooseAnalysisLookup`, rewritten `OnboardingWatchlistPage`, `App`/`Watchlists` highlight wiring — with Vitest tests alongside.
3. **E2E**: extend the Playwright happy-path to cover the real form + first-analysis + highlighted redirect.
4. **Verification**: run everything runnable in this environment (frontend suite), push, let CI run RSpec (no Ruby/Docker here, same constraint as the prior feature).

## 11. Files likely to change

| File | Change |
|---|---|
| `apps/control-plane/db/migrate/007_add_idempotency_key_to_watchlists.rb` | New |
| `apps/control-plane/app/models/watchlist.rb` | Add idempotency validation |
| `apps/control-plane/app/controllers/api/v1/watchlists_controller.rb` | Idempotency logic + rescue |
| `apps/control-plane/app/controllers/api/v1/me_controller.rb` | Strengthened onboarding check |
| `apps/control-plane/spec/requests/me_spec.rb` | Updated + new tests |
| `apps/control-plane/spec/requests/watchlists_spec.rb` | New (first dedicated file for this controller) |
| `apps/control-plane/spec/models/watchlist_spec.rb` | New |
| `packages/api-client/src/index.ts` | `createWatchlist` idempotency param |
| `apps/web/src/routes/OnboardingWatchlistPage.tsx` | Full rewrite |
| `apps/web/src/routes/chooseAnalysisLookup.ts` + `.test.ts` | New |
| `apps/web/src/main.tsx` | `App`/`Watchlists` highlight wiring, `ProtectedRoute` watchlist-id threading |
| `e2e/tests/happy-path.spec.ts` | Extended |

## 12. Acceptance criteria

1. Onboarding form requires name + target_kind + a real subject; cannot submit an empty-items watchlist through this flow.
2. Double-clicking submit (or a network retry with the same Idempotency-Key) creates exactly one watchlist, not two.
3. A watchlist created with zero items does not satisfy onboarding completion; one with ≥1 item does.
4. After creation, the user sees a real (possibly empty) first-analysis result — never fabricated data.
5. The user lands on the Watchlists dashboard tab with the new watchlist visible/highlighted, not Overview.
6. Existing dashboard "Add watchlist" mini-form and any other caller of `POST /api/v1/watchlists` without an Idempotency-Key behaves exactly as before.
7. Cross-tenant isolation holds: identical idempotency keys in different orgs never collide.
8. `pnpm typecheck && pnpm lint && pnpm test && pnpm build` and `bundle exec rspec` (via CI) all pass; Velato/Merzato/Policy Studio untouched.

## 13. Recommended next gstack command

`/plan-eng-review` was run on the prior onboarding feature and caught 10 real issues before implementation started — same value here given this touches the same `current_organization`/RBAC/idempotency surface area. That said, given this feature's scope is small and well-contained (one migration, one strengthened check, one idempotency addition to an existing endpoint, one frontend page rewrite), and per your explicit direction to continue straight into implementation, I'm proceeding now rather than gating on a separate review pass. Recommend `/review` (or a repeat `/plan-eng-review`) once implementation is committed, before opening a PR.
