import type {MeResponse} from "@signalchord/api-client";

export type Step =
  | {kind: "loading"}
  | {kind: "login"}
  | {kind: "workspace"; email: string; password: string}
  | {kind: "watchlist"; me: MeResponse}
  | {kind: "dashboard"; me: MeResponse};

// Pulled out of ProtectedRoute as a pure function so the onboarding-state ->
// UI-step mapping is unit-testable without a DOM/component-testing setup,
// matching this package's existing pure-function test convention.
export function stepForMe(me: MeResponse): Step {
  switch (me.onboarding_state) {
    case "first_watchlist_required":
      return {kind: "watchlist", me};
    case "complete":
      return {kind: "dashboard", me};
    case "verification_required":
    case "workspace_required":
      // Unreachable in practice: GET /api/v1/me only ever responds for a
      // caller who already authenticated, and authenticate_api_token! never
      // issues a session to an unverified or workspace-less user (backend
      // invariant). Falling back to "login" here is defensive, not a real
      // path — see me_controller.rb's own matching defensive comment.
      return {kind: "login"};
  }
}
