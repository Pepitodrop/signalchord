import {describe, expect, it} from "vitest";
import type {MeResponse} from "@signalchord/api-client";

import {stepForMe} from "./deriveStep";

function meWith(onboarding_state: MeResponse["onboarding_state"]): MeResponse {
  return {
    user: {id: "user-1", email: "member@example.com"},
    organization: {id: "org-1", name: "Acme", slug: "acme"},
    role: "admin",
    onboarding_state,
  };
}

describe("stepForMe", () => {
  it("routes to the watchlist onboarding step when first_watchlist_required", () => {
    const me = meWith("first_watchlist_required");
    expect(stepForMe(me)).toEqual({kind: "watchlist", me});
  });

  it("routes to the dashboard when complete", () => {
    const me = meWith("complete");
    expect(stepForMe(me)).toEqual({kind: "dashboard", me});
  });

  // Defensive coverage: GET /api/v1/me only ever responds for an already
  // -authenticated caller, so these two states should never actually arrive
  // here in practice (see the matching backend invariant in me_controller.rb
  // and deriveStep.ts's own comment). Proving the fallback is still correct
  // if that invariant were ever violated, rather than crashing or silently
  // showing the dashboard.
  it("falls back to login if verification_required somehow arrives", () => {
    expect(stepForMe(meWith("verification_required"))).toEqual({kind: "login"});
  });

  it("falls back to login if workspace_required somehow arrives", () => {
    expect(stepForMe(meWith("workspace_required"))).toEqual({kind: "login"});
  });
});
