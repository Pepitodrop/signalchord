import {useState} from "react";

import {
  DEFAULT_MERZATO_ARTWORK,
  DEFAULT_MERZATO_ASSEMBLY,
  MerzatoErrorInfo,
  MerzatoRunReport,
  merzatoErrorInfo,
  runMerzatoAssembly,
  runMerzatoArtwork,
} from "./merzatoStudio";
import {
  DEFAULT_SIGNAL_POLICY_INPUTS,
  MerzatoCoreDecision,
  SignalPolicyInputs,
  runMerzatoAlertTriage,
  runMerzatoContradictionGate,
  runMerzatoWatchlistRouting,
} from "./merzatoCorePolicies";
import "./merzatoCore.css";

const MERZATO_UPSTREAM = {
  repository: "https://github.com/Pepitodrop/merzato-lang",
  version: "1.3.0",
  commit: "79d4a04ccc2836fb0caaa1254d5b03aeb2a02b19",
} as const;

type CoreFeatureKey = "triage" | "routing" | "contradiction";

const CORE_FEATURES: Array<{
  key: CoreFeatureKey;
  number: number;
  title: string;
  description: string;
  action: string;
  run: (inputs: SignalPolicyInputs) => MerzatoCoreDecision;
}> = [
  {
    key: "triage",
    number: 3,
    title: "Alert triage scoring",
    description: "Calculates an auditable alert score and severity from trust, novelty, relevance, recency, corroboration, contradictions and watchlist status.",
    action: "Score signal",
    run: runMerzatoAlertTriage,
  },
  {
    key: "routing",
    number: 4,
    title: "Watchlist routing",
    description: "Routes matched entities to urgent, regional or observation queues using a Merzato speech program and deterministic register outputs.",
    action: "Route watchlist hit",
    run: runMerzatoWatchlistRouting,
  },
  {
    key: "contradiction",
    number: 5,
    title: "Contradiction safety gate",
    description: "Suppresses low-trust or contradiction-dominated signals and sends them to investigation routing without network or host capabilities.",
    action: "Evaluate gate",
    run: runMerzatoContradictionGate,
  },
];

const INPUT_FIELDS: Array<{
  key: keyof SignalPolicyInputs;
  label: string;
  min: number;
  max: number;
}> = [
  {key: "sourceTrust", label: "Source trust", min: 0, max: 100},
  {key: "corroborationCount", label: "Corroborations", min: 0, max: 20},
  {key: "contradictionCount", label: "Contradictions", min: 0, max: 20},
  {key: "novelty", label: "Novelty", min: 0, max: 100},
  {key: "entityRelevance", label: "Entity relevance", min: 0, max: 100},
  {key: "watchlistMatch", label: "Watchlist match", min: 0, max: 1},
  {key: "recency", label: "Recency", min: 0, max: 100},
  {key: "sourceDiversity", label: "Source diversity", min: 0, max: 100},
];

function ResultView({report}: {report: MerzatoRunReport}) {
  return (
    <div className="merzatoResult" aria-live="polite">
      <div className="merzatoMetrics">
        <span><b>{report.steps}</b><small>steps</small></span>
        <span><b>{report.instructions.length}</b><small>instructions</small></span>
        <span><b>{report.heapSize}</b><small>heap cells</small></span>
      </div>

      <div className="merzatoOutput">
        <small>Program output</small>
        <pre>{report.output || "(no output)"}</pre>
      </div>

      {report.score && (
        <div className="merzatoScore" aria-label="Merzato artwork MIDI notes">
          {report.score.map(note => (
            <span key={note.order} title={`Art block ${note.order}, MIDI note ${note.note}`}>
              <b>{note.note}</b>
              <small>#{note.order}</small>
            </span>
          ))}
        </div>
      )}

      <details>
        <summary>Validated instruction stream</summary>
        <pre>{report.instructions.map(instruction =>
          `${String(instruction.pc).padStart(3, "0")}  ${instruction.op.padEnd(7)} ${instruction.operands}`.trimEnd()
        ).join("\n")}</pre>
      </details>

      {report.compiledAssembly && (
        <details>
          <summary>Compiled Merzato Assembly</summary>
          <pre>{report.compiledAssembly}</pre>
        </details>
      )}
    </div>
  );
}

function ErrorView({error}: {error: MerzatoErrorInfo | null}) {
  if (!error) return null;
  const location = [
    error.line === undefined ? "" : `line ${error.line}`,
    error.artOrder === undefined ? "" : `art block ${error.artOrder}`,
    error.pc === undefined ? "" : `pc ${error.pc}`,
  ].filter(Boolean).join(" · ");

  return (
    <p className="error merzatoError" role="alert">
      <strong>{error.code}</strong>: {error.message}{location ? ` (${location})` : ""}
    </p>
  );
}

function DecisionView({decision}: {decision: MerzatoCoreDecision}) {
  return (
    <div className="merzatoDecision" aria-live="polite">
      <div className="merzatoDecisionMetrics">
        <span><b>{decision.alertScore}</b><small>alert score</small></span>
        <span><b>{decision.severityCode}</b><small>severity</small></span>
        <span><b>{decision.routingCode}</b><small>route</small></span>
        <span><b>{decision.suppressed ? "yes" : "no"}</b><small>suppressed</small></span>
      </div>
      <details className="merzatoSpeechSource">
        <summary>View executable Merzato speech (.merz)</summary>
        <pre>{decision.speechSource}</pre>
      </details>
      <ResultView report={decision.report}/>
    </div>
  );
}

function CorePolicyCard({
  feature,
  decision,
  error,
  onRun,
}: {
  feature: typeof CORE_FEATURES[number];
  decision: MerzatoCoreDecision | null;
  error: MerzatoErrorInfo | null;
  onRun: () => void;
}) {
  return (
    <section className="merzatoFeature merzatoCoreFeature">
      <p className="eyebrow">Main feature {feature.number}</p>
      <h3>{feature.title}</h3>
      <p className="muted">{feature.description}</p>
      <div className="merzatoActions">
        <button className="primary" type="button" onClick={onRun}>{feature.action}</button>
      </div>
      <ErrorView error={error}/>
      {decision && <DecisionView decision={decision}/>} 
    </section>
  );
}

export function MerzatoStudio() {
  const [assembly, setAssembly] = useState(DEFAULT_MERZATO_ASSEMBLY);
  const [artwork, setArtwork] = useState(DEFAULT_MERZATO_ARTWORK);
  const [assemblyReport, setAssemblyReport] = useState<MerzatoRunReport | null>(null);
  const [artworkReport, setArtworkReport] = useState<MerzatoRunReport | null>(null);
  const [assemblyError, setAssemblyError] = useState<MerzatoErrorInfo | null>(null);
  const [artworkError, setArtworkError] = useState<MerzatoErrorInfo | null>(null);
  const [policyInputs, setPolicyInputs] = useState<SignalPolicyInputs>(DEFAULT_SIGNAL_POLICY_INPUTS);
  const [decisions, setDecisions] = useState<Partial<Record<CoreFeatureKey, MerzatoCoreDecision>>>({});
  const [policyErrors, setPolicyErrors] = useState<Partial<Record<CoreFeatureKey, MerzatoErrorInfo>>>({});

  const executeAssembly = () => {
    setAssemblyError(null);
    try {
      setAssemblyReport(runMerzatoAssembly(assembly));
    } catch (error) {
      setAssemblyReport(null);
      setAssemblyError(merzatoErrorInfo(error));
    }
  };

  const executeArtwork = () => {
    setArtworkError(null);
    try {
      setArtworkReport(runMerzatoArtwork(artwork));
    } catch (error) {
      setArtworkReport(null);
      setArtworkError(merzatoErrorInfo(error));
    }
  };

  const executeCoreFeature = (feature: typeof CORE_FEATURES[number]) => {
    setPolicyErrors(current => ({...current, [feature.key]: undefined}));
    try {
      const decision = feature.run(policyInputs);
      setDecisions(current => ({...current, [feature.key]: decision}));
    } catch (error) {
      setDecisions(current => ({...current, [feature.key]: undefined}));
      setPolicyErrors(current => ({...current, [feature.key]: merzatoErrorInfo(error)}));
    }
  };

  return (
    <article className="card merzatoStudio">
      <div className="merzatoIntro">
        <div>
          <p className="eyebrow">Merzato programming language</p>
          <h2>Paint, compile and run bounded policy programs.</h2>
          <p className="muted">
            SignalChord embeds the Merzato 1.3 assembler, validator and speech compiler,
            then executes programs in a restricted local VM with no external host capabilities.
          </p>
        </div>
        <a href={MERZATO_UPSTREAM.repository} target="_blank" rel="noreferrer">
          Merzato {MERZATO_UPSTREAM.version} ↗
        </a>
      </div>

      <div className="merzatoGuardrails" aria-label="Merzato execution guardrails">
        <span>Local only</span>
        <span>10,000-step limit</span>
        <span>Bounded stack and heap</span>
        <span>Validated before execution</span>
      </div>

      <div className="merzatoFeatures">
        <section className="merzatoFeature">
          <p className="eyebrow">Main feature 1</p>
          <h3>Assembly policy runner</h3>
          <p className="muted">
            Write stable Merzato Assembly, validate labels and operands, run it deterministically,
            and inspect output, registers and the sealed instruction stream.
          </p>
          <label>
            Merzato Assembly (.mza)
            <textarea
              value={assembly}
              onChange={event => setAssembly(event.target.value)}
              spellCheck={false}
              aria-label="Merzato Assembly source"
            />
          </label>
          <div className="merzatoActions">
            <button className="primary" type="button" onClick={executeAssembly}>Run Assembly</button>
            <button type="button" onClick={() => {
              setAssembly(DEFAULT_MERZATO_ASSEMBLY);
              setAssemblyReport(null);
              setAssemblyError(null);
            }}>Reset example</button>
          </div>
          <ErrorView error={assemblyError}/>
          {assemblyReport && <ResultView report={assemblyReport}/>} 
        </section>

        <section className="merzatoFeature">
          <p className="eyebrow">Main feature 2</p>
          <h3>Executable artwork compiler</h3>
          <p className="muted">
            Convert ordered Piet-colour SVG blocks and MIDI note metadata into validated Merzato
            Assembly, execute it, and audit both the musical score and generated instructions.
          </p>
          <label>
            Ordered Merzato SVG
            <textarea
              value={artwork}
              onChange={event => setArtwork(event.target.value)}
              spellCheck={false}
              aria-label="Merzato SVG artwork source"
            />
          </label>
          <div className="merzatoActions">
            <button className="primary" type="button" onClick={executeArtwork}>Compile and run artwork</button>
            <button type="button" onClick={() => {
              setArtwork(DEFAULT_MERZATO_ARTWORK);
              setArtworkReport(null);
              setArtworkError(null);
            }}>Reset example</button>
          </div>
          <ErrorView error={artworkError}/>
          {artworkReport && <ResultView report={artworkReport}/>} 
        </section>
      </div>

      <section className="merzatoCoreWorkbench" aria-labelledby="merzato-core-heading">
        <div className="merzatoCoreHeader">
          <div>
            <p className="eyebrow">SignalChord core decision path</p>
            <h3 id="merzato-core-heading">Three production-shaped features written in Merzato speech.</h3>
          </div>
          <p className="muted">
            Inputs are compiled into immutable Merzato constants. Outputs use the same policy contract:
            r10 alert score, r11 severity, r12 routing and r13 suppression.
          </p>
        </div>

        <div className="merzatoInputGrid">
          {INPUT_FIELDS.map(field => (
            <label key={field.key}>
              {field.label}
              <input
                type="number"
                min={field.min}
                max={field.max}
                step={1}
                value={policyInputs[field.key]}
                onChange={event => setPolicyInputs(current => ({
                  ...current,
                  [field.key]: Number(event.target.value),
                }))}
              />
            </label>
          ))}
        </div>

        <div className="merzatoCoreFeatures">
          {CORE_FEATURES.map(feature => (
            <CorePolicyCard
              key={feature.key}
              feature={feature}
              decision={decisions[feature.key] ?? null}
              error={policyErrors[feature.key] ?? null}
              onRun={() => executeCoreFeature(feature)}
            />
          ))}
        </div>
      </section>

      <p className="muted merzatoProvenance">
        Upstream commit <code>{MERZATO_UPSTREAM.commit}</code>. The vendored assembler, validator,
        error and speech compiler modules retain the MIT license.
      </p>
    </article>
  );
}
