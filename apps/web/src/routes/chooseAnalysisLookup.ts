export type AnalysisLookupKind = "entity" | "search";

// entity-kind items carry an exact stable id (e.g. "company:acme"), best
// served by the direct entity lookup (GET /api/v1/entities/:id). topic/search
// items are closer to natural-language phrases, better served by full-text
// search (GET /api/v1/search). Pulled out as a pure function so the routing
// decision is unit-testable without a DOM/component-testing setup, matching
// deriveStep.ts's precedent in this package.
export function chooseAnalysisLookup(targetKind: string): AnalysisLookupKind {
  return targetKind === "entity" ? "entity" : "search";
}
