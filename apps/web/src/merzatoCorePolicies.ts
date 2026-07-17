import {runMerzatoAssembly} from "./merzatoStudio";
import type {MerzatoRunReport} from "./merzatoStudio";
import {transpileMerzSpeech} from "./vendor/merzato-lang/merzSpeech.js";

export type SignalPolicyInputs = {
  sourceTrust: number;
  corroborationCount: number;
  contradictionCount: number;
  novelty: number;
  entityRelevance: number;
  watchlistMatch: number;
  recency: number;
  sourceDiversity: number;
};

export type MerzatoCoreDecision = {
  feature: "alert-triage" | "watchlist-routing" | "contradiction-gate";
  speechSource: string;
  report: MerzatoRunReport;
  alertScore: number;
  severityCode: number;
  routingCode: number;
  suppressed: boolean;
};

export const DEFAULT_SIGNAL_POLICY_INPUTS: SignalPolicyInputs = {
  sourceTrust: 75,
  corroborationCount: 2,
  contradictionCount: 1,
  novelty: 80,
  entityRelevance: 90,
  watchlistMatch: 1,
  recency: 95,
  sourceDiversity: 60,
};

function boundedInteger(name: string, value: number, minimum: number, maximum: number): number {
  if (!Number.isFinite(value)) throw new Error(`${name} must be a finite number`);
  const integer = Math.round(value);
  if (integer < minimum || integer > maximum) {
    throw new Error(`${name} must be between ${minimum} and ${maximum}`);
  }
  return integer;
}

function normalizeInputs(inputs: SignalPolicyInputs): SignalPolicyInputs {
  return {
    sourceTrust: boundedInteger("Source trust", inputs.sourceTrust, 0, 100),
    corroborationCount: boundedInteger("Corroboration count", inputs.corroborationCount, 0, 20),
    contradictionCount: boundedInteger("Contradiction count", inputs.contradictionCount, 0, 20),
    novelty: boundedInteger("Novelty", inputs.novelty, 0, 100),
    entityRelevance: boundedInteger("Entity relevance", inputs.entityRelevance, 0, 100),
    watchlistMatch: boundedInteger("Watchlist match", inputs.watchlistMatch, 0, 1),
    recency: boundedInteger("Recency", inputs.recency, 0, 100),
    sourceDiversity: boundedInteger("Source diversity", inputs.sourceDiversity, 0, 100),
  };
}

function constants(inputs: SignalPolicyInputs): string {
  return `Wir nennen source_trust ab jetzt ${inputs.sourceTrust}.
Wir nennen corroboration_count ab jetzt ${inputs.corroborationCount}.
Wir nennen contradiction_count ab jetzt ${inputs.contradictionCount}.
Wir nennen novelty ab jetzt ${inputs.novelty}.
Wir nennen entity_relevance ab jetzt ${inputs.entityRelevance}.
Wir nennen watchlist_match ab jetzt ${inputs.watchlistMatch}.
Wir nennen recency ab jetzt ${inputs.recency}.
Wir nennen source_diversity ab jetzt ${inputs.sourceDiversity}.`;
}

export function buildAlertTriagePolicy(rawInputs: SignalPolicyInputs): string {
  const inputs = normalizeInputs(rawInputs);
  return `Die Regierung beginnt bei main.
${constants(inputs)}

Zum Tagesordnungspunkt main.
  Wir brauchen jetzt $source_trust.
  Wir brauchen jetzt $novelty.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $entity_relevance.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $recency.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $source_diversity.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt 5.
  Wir teilen das durch, solide finanziert.
  Wir brauchen jetzt $corroboration_count.
  Wir brauchen jetzt 5.
  Wir vervielfachen das für den Wirtschaftsstandort.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $watchlist_match.
  Wir brauchen jetzt 15.
  Wir vervielfachen das für den Wirtschaftsstandort.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $contradiction_count.
  Wir brauchen jetzt 20.
  Wir vervielfachen das für den Wirtschaftsstandort.
  Wir ziehen das ab, damit der Haushalt stimmt.
  Das kommt jetzt in das Ministerium r10.

  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r13.
  Aus dem Ministerium r10 wird geliefert.
  Wir brauchen jetzt 85.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu mittel.
  Wir brauchen jetzt 3.
  Das kommt jetzt in das Ministerium r11.
  Wir gehen jetzt ohne weitere Debatte zu routing.

Zum Tagesordnungspunkt mittel.
  Aus dem Ministerium r10 wird geliefert.
  Wir brauchen jetzt 60.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu niedrig.
  Wir brauchen jetzt 2.
  Das kommt jetzt in das Ministerium r11.
  Wir gehen jetzt ohne weitere Debatte zu routing.

Zum Tagesordnungspunkt niedrig.
  Aus dem Ministerium r10 wird geliefert.
  Wir brauchen jetzt 35.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu minimal.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r11.
  Wir gehen jetzt ohne weitere Debatte zu routing.

Zum Tagesordnungspunkt minimal.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r11.

Zum Tagesordnungspunkt routing.
  Wir brauchen jetzt $watchlist_match.
  Wenn das null ist, gehen wir zu widerspruch.
  Wir brauchen jetzt 7.
  Das kommt jetzt in das Ministerium r12.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt widerspruch.
  Wir brauchen jetzt $contradiction_count.
  Wenn das null ist, gehen wir zu normal.
  Wir brauchen jetzt 5.
  Das kommt jetzt in das Ministerium r12.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt normal.
  Wir brauchen jetzt 2.
  Das kommt jetzt in das Ministerium r12.

Zum Tagesordnungspunkt ende.
  Aus dem Ministerium r10 wird geliefert.
  Die Zahl muss jetzt raus.
  Aber ohne Bubatz.`;
}

export function buildWatchlistRoutingPolicy(rawInputs: SignalPolicyInputs): string {
  const inputs = normalizeInputs(rawInputs);
  return `Die Regierung beginnt bei main.
${constants(inputs)}

Zum Tagesordnungspunkt main.
  Wir brauchen jetzt $watchlist_match.
  Wenn das null ist, gehen wir zu kein_treffer.
  Wir brauchen jetzt $entity_relevance.
  Wir brauchen jetzt $recency.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $source_trust.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt 3.
  Wir teilen das durch, solide finanziert.
  Das kommt jetzt in das Ministerium r10.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r13.

  Aus dem Ministerium r10 wird geliefert.
  Wir brauchen jetzt 80.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu regional.
  Wir brauchen jetzt 3.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 7.
  Das kommt jetzt in das Ministerium r12.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt regional.
  Aus dem Ministerium r10 wird geliefert.
  Wir brauchen jetzt 60.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu beobachtung.
  Wir brauchen jetzt 2.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 4.
  Das kommt jetzt in das Ministerium r12.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt beobachtung.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r12.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt kein_treffer.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r10.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r12.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r13.

Zum Tagesordnungspunkt ende.
  Aus dem Ministerium r12 wird geliefert.
  Die Zahl muss jetzt raus.
  Aber ohne Bubatz.`;
}

export function buildContradictionGatePolicy(rawInputs: SignalPolicyInputs): string {
  const inputs = normalizeInputs(rawInputs);
  return `Die Regierung beginnt bei main.
${constants(inputs)}

Zum Tagesordnungspunkt main.
  Wir brauchen jetzt $source_trust.
  Wir brauchen jetzt $corroboration_count.
  Wir brauchen jetzt 10.
  Wir vervielfachen das für den Wirtschaftsstandort.
  Wir rechnen das zusammen, denn Leistung muss sich lohnen.
  Wir brauchen jetzt $contradiction_count.
  Wir brauchen jetzt 15.
  Wir vervielfachen das für den Wirtschaftsstandort.
  Wir ziehen das ab, damit der Haushalt stimmt.
  Das kommt jetzt in das Ministerium r10.

  Wir brauchen jetzt $contradiction_count.
  Wir brauchen jetzt $corroboration_count.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu vertrauen.
  Wir gehen jetzt ohne weitere Debatte zu unterdruecken.

Zum Tagesordnungspunkt vertrauen.
  Wir brauchen jetzt 40.
  Wir brauchen jetzt $source_trust.
  Wir prüfen, ob das erste größer ist.
  Wenn das null ist, gehen wir zu freigeben.

Zum Tagesordnungspunkt unterdruecken.
  Wir brauchen jetzt 3.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 5.
  Das kommt jetzt in das Ministerium r12.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r13.
  Wir gehen jetzt ohne weitere Debatte zu ende.

Zum Tagesordnungspunkt freigeben.
  Wir brauchen jetzt 1.
  Das kommt jetzt in das Ministerium r11.
  Wir brauchen jetzt 2.
  Das kommt jetzt in das Ministerium r12.
  Wir brauchen jetzt 0.
  Das kommt jetzt in das Ministerium r13.

Zum Tagesordnungspunkt ende.
  Aus dem Ministerium r13 wird geliefert.
  Die Zahl muss jetzt raus.
  Aber ohne Bubatz.`;
}

function registerNumber(report: MerzatoRunReport, index: number): number {
  const value = Number(report.registers[index]);
  if (!Number.isSafeInteger(value)) throw new Error(`Merzato register r${index} did not contain a safe integer`);
  return value;
}

function runDecision(
  feature: MerzatoCoreDecision["feature"],
  speechSource: string,
): MerzatoCoreDecision {
  const compiledAssembly = transpileMerzSpeech(speechSource);
  const assemblyReport = runMerzatoAssembly(compiledAssembly);
  const report: MerzatoRunReport = {...assemblyReport, compiledAssembly};
  return {
    feature,
    speechSource,
    report,
    alertScore: registerNumber(report, 10),
    severityCode: registerNumber(report, 11),
    routingCode: registerNumber(report, 12),
    suppressed: registerNumber(report, 13) !== 0,
  };
}

export function runMerzatoAlertTriage(inputs: SignalPolicyInputs): MerzatoCoreDecision {
  return runDecision("alert-triage", buildAlertTriagePolicy(inputs));
}

export function runMerzatoWatchlistRouting(inputs: SignalPolicyInputs): MerzatoCoreDecision {
  return runDecision("watchlist-routing", buildWatchlistRoutingPolicy(inputs));
}

export function runMerzatoContradictionGate(inputs: SignalPolicyInputs): MerzatoCoreDecision {
  return runDecision("contradiction-gate", buildContradictionGatePolicy(inputs));
}
