import {useState} from "react";

import {
  DEFAULT_MERZATO_ARTWORK,
  DEFAULT_MERZATO_ASSEMBLY,
  MERZATO_UPSTREAM,
  MerzatoErrorInfo,
  MerzatoRunReport,
  merzatoErrorInfo,
  runMerzatoAssembly,
  runMerzatoArtwork,
} from "./merzatoStudio";

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

export function MerzatoStudio() {
  const [assembly, setAssembly] = useState(DEFAULT_MERZATO_ASSEMBLY);
  const [artwork, setArtwork] = useState(DEFAULT_MERZATO_ARTWORK);
  const [assemblyReport, setAssemblyReport] = useState<MerzatoRunReport | null>(null);
  const [artworkReport, setArtworkReport] = useState<MerzatoRunReport | null>(null);
  const [assemblyError, setAssemblyError] = useState<MerzatoErrorInfo | null>(null);
  const [artworkError, setArtworkError] = useState<MerzatoErrorInfo | null>(null);

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

  return (
    <article className="card merzatoStudio">
      <div className="merzatoIntro">
        <div>
          <p className="eyebrow">Merzato programming language</p>
          <h2>Paint, compile and run bounded policy programs.</h2>
          <p className="muted">
            SignalChord embeds the Merzato 1.x assembler and validator from the upstream project,
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

      <p className="muted merzatoProvenance">
        Upstream commit <code>{MERZATO_UPSTREAM.commit}</code>. The vendored assembler and validator retain the MIT license.
      </p>
    </article>
  );
}
