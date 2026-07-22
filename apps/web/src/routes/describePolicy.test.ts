import {describe, expect, it} from "vitest";

import {describePolicy} from "./describePolicy";

describe("describePolicy", () => {
  it("names the policy when one is linked", () => {
    expect(describePolicy("Watchlist Novelty")).toBe("Triggered policy: Watchlist Novelty.");
  });

  it("shows an honest fallback when no policy is linked (null)", () => {
    expect(describePolicy(null)).toBe("Not linked to a specific policy.");
  });

  it("shows the same honest fallback when policy_name is undefined", () => {
    expect(describePolicy(undefined)).toBe("Not linked to a specific policy.");
  });
});
