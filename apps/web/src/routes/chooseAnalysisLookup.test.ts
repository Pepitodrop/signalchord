import {describe, expect, it} from "vitest";

import {chooseAnalysisLookup} from "./chooseAnalysisLookup";

describe("chooseAnalysisLookup", () => {
  it("routes entity-kind items to the direct entity lookup", () => {
    expect(chooseAnalysisLookup("entity")).toBe("entity");
  });

  it("routes topic-kind items to full-text search", () => {
    expect(chooseAnalysisLookup("topic")).toBe("search");
  });

  it("routes search-kind items to full-text search", () => {
    expect(chooseAnalysisLookup("search")).toBe("search");
  });
});
