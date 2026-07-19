import {useEffect, useState} from "react";

import {MerzSpeechReader} from "./MerzSpeechReader";

const SPEECH_PROGRAMS = [
  {
    id: "meme-cabinet",
    title: "Complete meme cabinet",
    path: "/programs/merz/meme-cabinet.merz",
    description: "Long executable satire with the documented meme vocabulary and the callable helfer function.",
  },
  {
    id: "graph-growth-briefing",
    title: "Graph growth briefing",
    path: "/programs/merz/graph-growth-briefing.merz",
    description: "A shorter policy speech with the callable graph_score function.",
  },
] as const;

export function MerzSpeechLibrary() {
  const [selectedId, setSelectedId] = useState<(typeof SPEECH_PROGRAMS)[number]["id"]>("meme-cabinet");
  const [source, setSource] = useState("");
  const [error, setError] = useState("");
  const selected = SPEECH_PROGRAMS.find(program => program.id === selectedId) ?? SPEECH_PROGRAMS[0];

  useEffect(() => {
    const controller = new AbortController();
    setSource("");
    setError("");
    void fetch(selected.path, {signal: controller.signal})
      .then(response => {
        if (!response.ok) throw new Error(`Speech source returned ${response.status}`);
        return response.text();
      })
      .then(setSource)
      .catch(fetchError => {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") return;
        setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
      });
    return () => controller.abort();
  }, [selected.path]);

  return (
    <article className="card merzSpeechLibrary">
      <div className="merzatoIntro">
        <div>
          <p className="eyebrow">Merzato speech reader</p>
          <h2>Translate executable .merz code into a readable speech.</h2>
          <p className="muted">
            Structural labels, constants, calls and jumps become natural German sentences. The original
            executable source remains visible and unchanged.
          </p>
        </div>
        <label>
          Speech program
          <select value={selectedId} onChange={event => setSelectedId(event.target.value as typeof selectedId)}>
            {SPEECH_PROGRAMS.map(program => <option key={program.id} value={program.id}>{program.title}</option>)}
          </select>
        </label>
      </div>

      <p className="muted">{selected.description}</p>
      {error && <p className="error" role="alert">{error}</p>}
      {!error && !source && <p className="muted">Loading speech source…</p>}
      {source && (
        <>
          <MerzSpeechReader source={source}/>
          <details className="merzatoSpeechSource">
            <summary>View original executable {selected.id}.merz</summary>
            <pre>{source}</pre>
          </details>
        </>
      )}
    </article>
  );
}
