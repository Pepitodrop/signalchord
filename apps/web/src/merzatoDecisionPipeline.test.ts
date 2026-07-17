import {describe, expect, it} from "vitest";

import {DEFAULT_SIGNAL_POLICY_INPUTS} from "./merzatoCorePolicies";
import {runMerzatoDecisionPipeline} from "./merzatoDecisionPipeline";

describe("Merzato decision pipeline", () => {
  it("selects watchlist routing for a valid matched signal", () => {
    const pipeline = runMerzatoDecisionPipeline(DEFAULT_SIGNAL_POLICY_INPUTS);

    expect(pipeline.finalDecision.feature).toBe("watchlist-routing");
    expect(pipeline.finalDecision.routingCode).toBe(7);
    expect(pipeline.finalDecision.suppressed).toBe(false);
    expect(pipeline.reason).toContain("watchlist match");
  });

  it("gives contradiction suppression the highest precedence", () => {
    const pipeline = runMerzatoDecisionPipeline({
      ...DEFAULT_SIGNAL_POLICY_INPUTS,
      sourceTrust: 30,
      corroborationCount: 1,
      contradictionCount: 3,
    });

    expect(pipeline.finalDecision.feature).toBe("contradiction-gate");
    expect(pipeline.finalDecision.routingCode).toBe(5);
    expect(pipeline.finalDecision.suppressed).toBe(true);
    expect(pipeline.reason).toContain("takes precedence");
  });

  it("falls back to triage when no watchlist route or safety suppression applies", () => {
    const pipeline = runMerzatoDecisionPipeline({
      ...DEFAULT_SIGNAL_POLICY_INPUTS,
      watchlistMatch: 0,
    });

    expect(pipeline.watchlist.suppressed).toBe(true);
    expect(pipeline.contradiction.suppressed).toBe(false);
    expect(pipeline.finalDecision.feature).toBe("alert-triage");
    expect(pipeline.reason).toContain("alert triage");
  });

  it("executes all three bounded Merzato programs", () => {
    const pipeline = runMerzatoDecisionPipeline(DEFAULT_SIGNAL_POLICY_INPUTS);

    expect(pipeline.triage.report.steps).toBeGreaterThan(0);
    expect(pipeline.watchlist.report.steps).toBeGreaterThan(0);
    expect(pipeline.contradiction.report.steps).toBeGreaterThan(0);
  });
});
