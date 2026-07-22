import {describe, expect, it} from "vitest";

import {describeEvidenceCount, EVIDENCE_DISCLOSURE_LABEL} from "./describeEvidence";

describe("describeEvidenceCount", () => {
  it("reports a calm, non-error empty state when there is no evidence", () => {
    expect(describeEvidenceCount([])).toBe("No evidence indexed yet for this one.");
  });

  it("uses singular phrasing for exactly one evidence record", () => {
    expect(describeEvidenceCount(["ev-1"])).toBe("1 evidence record referenced.");
  });

  it("uses plural phrasing for more than one evidence record", () => {
    expect(describeEvidenceCount(["ev-1", "ev-2", "ev-3"])).toBe("3 evidence records referenced.");
  });
});

describe("EVIDENCE_DISCLOSURE_LABEL", () => {
  it("frames the raw-ID disclosure as a stated limitation, not a bare dump", () => {
    expect(EVIDENCE_DISCLOSURE_LABEL).toMatch(/content lookup not yet available/);
  });
});
