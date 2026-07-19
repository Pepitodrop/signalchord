import {useEffect, useMemo, useRef, useState} from "react";

import {
  estimateSpeechSeconds,
  merzSourceToSpeech,
  merzSourceToSpeechParagraphs,
  splitSpeechIntoChunks,
} from "./merzSpeech";

type SpeechQueue = {
  generation: number;
  chunks: string[];
  index: number;
};

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function germanVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  return voices.find(voice => voice.lang.toLowerCase() === "de-de")
    ?? voices.find(voice => voice.lang.toLowerCase().startsWith("de"))
    ?? null;
}

export function MerzSpeechReader({source}: {source: string}) {
  const paragraphs = useMemo(() => merzSourceToSpeechParagraphs(source), [source]);
  const transcript = useMemo(() => merzSourceToSpeech(source), [source]);
  const chunks = useMemo(() => splitSpeechIntoChunks(transcript), [transcript]);
  const duration = useMemo(() => estimateSpeechSeconds(transcript), [transcript]);
  const queue = useRef<SpeechQueue>({generation: 0, chunks: [], index: 0});
  const [speaking, setSpeaking] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  const stop = () => {
    queue.current.generation += 1;
    window.speechSynthesis?.cancel();
    setSpeaking(false);
    setProgress(0);
  };

  useEffect(() => stop, []);

  const speak = () => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      setError("Text-to-speech is not available in this browser. The translated speech remains readable below.");
      return;
    }
    if (!chunks.length) {
      setError("This Merzato source did not produce a readable speech transcript.");
      return;
    }

    stop();
    setError("");
    setSpeaking(true);
    const generation = queue.current.generation;
    queue.current = {generation, chunks, index: 0};

    const playNext = () => {
      const current = queue.current;
      if (current.generation !== generation) return;
      if (current.index >= current.chunks.length) {
        setSpeaking(false);
        setProgress(100);
        return;
      }

      const utterance = new SpeechSynthesisUtterance(current.chunks[current.index]);
      const voice = germanVoice();
      utterance.lang = voice?.lang ?? "de-DE";
      if (voice) utterance.voice = voice;
      utterance.rate = 0.92;
      utterance.pitch = 0.92;
      utterance.volume = 1;
      utterance.onend = () => {
        if (queue.current.generation !== generation) return;
        queue.current.index += 1;
        setProgress(Math.round(queue.current.index / queue.current.chunks.length * 100));
        playNext();
      };
      utterance.onerror = event => {
        if (event.error === "canceled" || event.error === "interrupted") return;
        setSpeaking(false);
        setError(`Speech playback stopped: ${event.error}. You can still read the transcript below.`);
      };
      window.speechSynthesis.speak(utterance);
    };

    playNext();
  };

  return (
    <section className="merzSpeechReader" aria-label="Readable Merzato speech">
      <div className="merzSpeechReaderHeader">
        <div>
          <strong>Readable speech translation</strong>
          <small>German browser voice · approximately {formatDuration(duration)}</small>
        </div>
        <div className="merzatoActions">
          <button className="primary" type="button" onClick={speaking ? stop : speak}>
            {speaking ? "■ Stop speech" : "🔊 Read speech aloud"}
          </button>
        </div>
      </div>
      <div className="merzSpeechProgress" aria-label={`Speech progress ${progress}%`}>
        <span style={{width: `${progress}%`}}/>
      </div>
      {error && <p className="error merzatoError" role="alert">{error}</p>}
      <details>
        <summary>Read translated speech as text</summary>
        <div className="merzSpeechTranscript">
          {paragraphs.map((paragraph, index) => <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>)}
        </div>
      </details>
    </section>
  );
}
