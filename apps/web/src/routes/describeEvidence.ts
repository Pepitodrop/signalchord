// Pure derivation of the alert detail pane's evidence section copy — pulled
// out so the 0/1/N and disclosed-limitation framing is unit-testable without
// a DOM/component-testing setup, matching this package's existing convention
// (chooseAnalysisLookup.ts, deriveStep.ts).
//
// Evidence IDs today are opaque strings with no content-resolution endpoint
// (see docs/specs/explainable-alert-feed.md TODOS #1) — the raw-ID disclosure
// is framed as a stated limitation, not a bare unlabeled dump, so it reads as
// disclosed transparency rather than something broken or unfinished.
export const EVIDENCE_DISCLOSURE_LABEL = "Raw evidence references (IDs only — content lookup not yet available)";

export function describeEvidenceCount(evidenceIds: string[]): string {
  if (evidenceIds.length === 0) return "No evidence indexed yet for this one.";
  return `${evidenceIds.length} evidence record${evidenceIds.length === 1 ? "" : "s"} referenced.`;
}
