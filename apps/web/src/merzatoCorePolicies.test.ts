import {describe, expect, it} from "vitest";

import {
  DEFAULT_SIGNAL_POLICY_INPUTS,
  buildAlertTriagePolicy,
  runMerzatoAlertTriage,
  runMerzatoContradictionGate,
  runMerzatoWatchlistRouting,
} from "./merzatoCorePolicies";

 describe("Merzato core policies", () => {
  it("scores alert triage through executable Merzato speech", () => {
    const source = buildAlertTriagePolicy(DEFAULT_SIGNAL_POLICY_INPUTS);
    const decision = runMerzatoAlertTriage(DEFAULT_SIGNAL_POLICY_INPUTS);

    expect(source).toContain("Wir nennen source_trust ab jetzt 75.");
    expect(source).toContain("Aber ohne Bubatz.");
    expect(decision.alertScore).toBe(85);
    expect(decision.severityCode).toBe(2);
    expect(decision.routingCode).toBe(7);
    expect(decision.suppressed).toBe(false);
    expect(decision.report.output).toBe("85");
    expect(decision.report.compiledAssembly).toContain(".const source_trust 75");
    expect(decision.report.compiledAssembly).toContain("store r10");
  });

  it("routes strong watchlist matches to the urgent queue", () => {
    const decision = runMerzatoWatchlistRouting(DEFAULT_SIGNAL_POLICY_INPUTS);

    expect(decision.alertScore).toBe(86);
    expect(decision.severityCode).toBe(3);
    expect(decision.routingCode).toBe(7);
    expect(decision.suppressed).toBe(false);
    expect(decision.report.output).toBe("7");
  });

  it("suppresses signals without a watchlist match", () => {
    const decision = runMerzatoWatchlistRouting({
      ...DEFAULT_SIGNAL_POLICY_INPUTS,
      watchlistMatch: 0,
    });

    expect(decision.alertScore).toBe(0);
    expect(decision.severityCode).toBe(0);
    expect(decision.routingCode).toBe(0);
    expect(decision.suppressed).toBe(true);
  });

  it("gates contradiction-dominated or low-trust signals", () => {
    const decision = runMerzatoContradictionGate({
      ...DEFAULT_SIGNAL_POLICY_INPUTS,
      sourceTrust: 30,
      corroborationCount: 1,
      contradictionCount: 3,
    });

    expect(decision.alertScore).toBe(-5);
    expect(decision.severityCode).toBe(3);
    expect(decision.routingCode).toBe(5);
    expect(decision.suppressed).toBe(true);
    expect(decision.report.output).toBe("1");
  });

  it("rejects policy inputs outside the documented bounds", () => {
    expect(() => runMerzatoAlertTriage({
      ...DEFAULT_SIGNAL_POLICY_INPUTS,
      sourceTrust: 101,
    })).toThrow("Source trust must be between 0 and 100");
  });
});
