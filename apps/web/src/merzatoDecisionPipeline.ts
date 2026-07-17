import {
  MerzatoCoreDecision,
  SignalPolicyInputs,
  runMerzatoAlertTriage,
  runMerzatoContradictionGate,
  runMerzatoWatchlistRouting,
} from "./merzatoCorePolicies";

export type MerzatoDecisionPipeline = {
  triage: MerzatoCoreDecision;
  watchlist: MerzatoCoreDecision;
  contradiction: MerzatoCoreDecision;
  finalDecision: MerzatoCoreDecision;
  reason: string;
};

export function runMerzatoDecisionPipeline(inputs: SignalPolicyInputs): MerzatoDecisionPipeline {
  const triage = runMerzatoAlertTriage(inputs);
  const watchlist = runMerzatoWatchlistRouting(inputs);
  const contradiction = runMerzatoContradictionGate(inputs);

  if (contradiction.suppressed) {
    return {
      triage,
      watchlist,
      contradiction,
      finalDecision: contradiction,
      reason: "The contradiction safety gate takes precedence because it suppressed the signal.",
    };
  }

  if (!watchlist.suppressed) {
    return {
      triage,
      watchlist,
      contradiction,
      finalDecision: watchlist,
      reason: "A valid watchlist match takes precedence over generic alert triage.",
    };
  }

  return {
    triage,
    watchlist,
    contradiction,
    finalDecision: triage,
    reason: "No safety suppression or watchlist route applied, so alert triage is the final decision.",
  };
}
