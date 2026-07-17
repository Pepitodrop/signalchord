import {useCallback, useEffect, useMemo, useRef, useState} from "react";

import {MerzatoStudio} from "./MerzatoStudio";
import {
  buildVelatoPlaybackEvents,
  encodeVelatoMidi,
  midiFrequency,
  VELATO_SHOWCASE_PROGRAMS,
  VelatoShowcaseProgram,
} from "./velatoShowcase";

type ActivePlayback = {
  id: string;
  context: AudioContext;
  timeout: number;
};

const BANK_VOICES: readonly OscillatorType[] = ["triangle", "sine", "square", "sawtooth"];

function downloadMidi(program: VelatoShowcaseProgram) {
  const bytes = encodeVelatoMidi(program);
  const blob = new Blob([bytes], {type: "audio/midi"});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = program.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function ProgramCard({
  program,
  playing,
  onToggle,
}: {
  program: VelatoShowcaseProgram;
  playing: boolean;
  onToggle: (program: VelatoShowcaseProgram) => void;
}) {
  const events = useMemo(() => buildVelatoPlaybackEvents(program), [program]);

  return (
    <section className={`velatoProgram ${playing ? "playing" : ""}`}>
      <div className="velatoProgramHeader">
        <div>
          <p className="eyebrow">Route {program.route} · {program.meter} · {program.tempo} BPM</p>
          <h3>{program.title}</h3>
          <small>{program.style}</small>
        </div>
        <span className="velatoRoute" aria-label={`Routing code ${program.route}`}>{program.route}</span>
      </div>

      <div className="velatoNotes" aria-label={`${program.title} executable MIDI notes`}>
        {events.map((event, index) => (
          <span
            key={`${program.id}-${index}`}
            className={`velatoNote bank${event.bank}`}
            title={`${event.operation}${event.operand ? ` ${event.operand}` : ""} · bank ${event.bank} · interval ${event.interval}`}
          >
            <b>{event.noteName}</b>
            <small>B{event.bank}</small>
          </span>
        ))}
      </div>

      <div className="velatoPlayer">
        <button
          className="primary"
          type="button"
          aria-pressed={playing}
          onClick={() => onToggle(program)}
        >
          {playing ? "■ Stop code" : "▶ Play code"}
        </button>
        <button type="button" onClick={() => downloadMidi(program)}>Download .mid</button>
        <small>{events.length} executable instructions</small>
      </div>

      <p className="velatoPurpose"><strong>What it does:</strong> {program.purpose}</p>
      <p className="muted velatoPlaybackNote">
        The note order comes directly from the checked-in Velato source. MIDI banks are rendered as different synth voices, while the downloadable file preserves the real opcode channels, intervals and operands.
      </p>

      <details>
        <summary>View executable {program.id}.vasm</summary>
        <pre>{program.source}</pre>
      </details>
    </section>
  );
}

export function VelatoShowcase() {
  const [revealed, setRevealed] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [audioError, setAudioError] = useState("");
  const active = useRef<ActivePlayback | null>(null);

  const stop = useCallback(() => {
    const current = active.current;
    if (!current) return;
    window.clearTimeout(current.timeout);
    void current.context.close();
    active.current = null;
    setPlayingId(null);
  }, []);

  useEffect(() => stop, [stop]);

  const toggle = useCallback(async (program: VelatoShowcaseProgram) => {
    if (active.current?.id === program.id) {
      stop();
      return;
    }

    stop();
    setAudioError("");

    try {
      const context = new AudioContext();
      if (context.state === "suspended") await context.resume();

      const events = buildVelatoPlaybackEvents(program);
      const master = context.createGain();
      master.gain.setValueAtTime(0.13, context.currentTime);
      master.connect(context.destination);

      const secondsPerBeat = 60 / program.tempo;
      let cursor = context.currentTime + 0.06;

      for (const event of events) {
        const duration = Math.max(0.045, event.durationBeats * secondsPerBeat);
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const filter = context.createBiquadFilter();

        oscillator.type = BANK_VOICES[event.bank] ?? "triangle";
        oscillator.frequency.setValueAtTime(midiFrequency(event.midi), cursor);
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(1800 + event.bank * 650, cursor);
        gain.gain.setValueAtTime(0.0001, cursor);
        gain.gain.exponentialRampToValueAtTime(0.055 * event.accent, cursor + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, cursor + duration * 0.9);

        oscillator.connect(filter);
        filter.connect(gain);
        gain.connect(master);
        oscillator.start(cursor);
        oscillator.stop(cursor + duration);
        cursor += duration;
      }

      const timeout = window.setTimeout(() => {
        void context.close();
        active.current = null;
        setPlayingId(null);
      }, Math.max(0, (cursor - context.currentTime + 0.08) * 1000));

      active.current = {id: program.id, context, timeout};
      setPlayingId(program.id);
    } catch {
      setAudioError("Audio playback is unavailable in this browser. The executable MIDI download still works.");
    }
  }, [stop]);

  return (
    <>
      <article className="card velatoShowcase">
        <div className="velatoShowcaseIntro">
          <div>
            <p className="eyebrow">Velato easter egg</p>
            <h2>The policies are also playable scores.</h2>
            <p className="muted">
              Reveal the five functional programs and hear their actual instruction streams.
            </p>
          </div>
          <button
            className="velatoReveal"
            type="button"
            aria-expanded={revealed}
            onClick={() => {
              if (revealed) stop();
              setRevealed(value => !value);
            }}
          >
            {revealed ? "Hide scores" : "♪ Reveal scores"}
          </button>
        </div>

        {audioError && <p className="error">{audioError}</p>}

        {revealed && (
          <div className="velatoPrograms">
            {VELATO_SHOWCASE_PROGRAMS.map(program => (
              <ProgramCard
                key={program.id}
                program={program}
                playing={playingId === program.id}
                onToggle={programToPlay => void toggle(programToPlay)}
              />
            ))}
          </div>
        )}
      </article>
      <MerzatoStudio/>
    </>
  );
}
