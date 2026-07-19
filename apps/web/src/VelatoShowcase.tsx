import {useCallback, useEffect, useMemo, useRef, useState} from "react";

import {
  createAudibleMaster,
  createUnlockedAudioContext,
  scheduleAudibleTone,
} from "./browserAudio";
import {MerzatoStudio} from "./MerzatoStudio";
import {
  buildVelatoPlaybackEvents,
  encodeVelatoMidi,
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
        Playback transposes low notes one octave for phone speakers and adds a quiet octave layer.
        The exported MIDI retains the exact executable channels, intervals, velocities and operands.
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
  const [volume, setVolume] = useState(0.82);
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
      const context = await createUnlockedAudioContext();
      const events = buildVelatoPlaybackEvents(program);
      const master = createAudibleMaster(context, volume);
      const secondsPerBeat = 60 / program.tempo;
      let cursor = context.currentTime + 0.035;

      for (const event of events) {
        const duration = Math.max(0.075, event.durationBeats * secondsPerBeat);
        scheduleAudibleTone({
          context,
          output: master,
          midi: event.midi,
          voice: BANK_VOICES[event.bank] ?? "triangle",
          start: cursor,
          duration,
          accent: event.accent,
        });
        cursor += duration;
      }

      const timeout = window.setTimeout(() => {
        void context.close();
        active.current = null;
        setPlayingId(null);
      }, Math.max(0, (cursor - context.currentTime + 0.1) * 1000));

      active.current = {id: program.id, context, timeout};
      setPlayingId(program.id);
    } catch (error) {
      setAudioError(error instanceof Error
        ? error.message
        : "Audio playback is unavailable. Check the device media volume and browser permission.");
    }
  }, [stop, volume]);

  return (
    <>
      <article className="card velatoShowcase">
        <div className="velatoShowcaseIntro">
          <div>
            <p className="eyebrow">Velato easter egg</p>
            <h2>The policies are also playable scores.</h2>
            <p className="muted">
              Reveal the six functional programs and hear their actual instruction streams.
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

        {revealed && (
          <label className="velatoVolume">
            Playback volume
            <input
              type="range"
              min="0.2"
              max="1"
              step="0.05"
              value={volume}
              onChange={event => setVolume(Number(event.target.value))}
              aria-label="Velato playback volume"
            />
            <span>{Math.round(volume * 100)}%</span>
          </label>
        )}

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
