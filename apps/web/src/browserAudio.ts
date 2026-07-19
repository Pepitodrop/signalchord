export const PLAYBACK_TRANSPOSE_SEMITONES = 12;

export type BrowserAudioContext = AudioContext & {
  webkitAudioContext?: never;
};

type AudioContextConstructor = new (options?: AudioContextOptions) => AudioContext;

declare global {
  interface Window {
    webkitAudioContext?: AudioContextConstructor;
  }
}

export function audibleMidi(midi: number): number {
  const normalized = Math.max(0, Math.min(127, Math.round(midi)));
  const transposed = normalized + PLAYBACK_TRANSPOSE_SEMITONES;
  return transposed <= 96 ? transposed : normalized;
}

export async function createUnlockedAudioContext(): Promise<AudioContext> {
  const AudioContextClass = window.AudioContext ?? window.webkitAudioContext;
  if (!AudioContextClass) throw new Error("This browser does not provide the Web Audio API.");

  const context = new AudioContextClass({latencyHint: "interactive"});

  // Mobile Safari and some Android WebViews require an actual source to be started
  // inside the click gesture before the context will reliably leave suspended state.
  const unlockBuffer = context.createBuffer(1, 1, context.sampleRate);
  const unlockSource = context.createBufferSource();
  unlockSource.buffer = unlockBuffer;
  unlockSource.connect(context.destination);
  unlockSource.start(0);

  if (context.state === "suspended") await context.resume();
  if (context.state !== "running") {
    await context.close();
    throw new Error("The browser kept audio playback suspended. Check the device media volume and browser audio permission.");
  }

  return context;
}

export function createAudibleMaster(context: AudioContext, volume = 0.82): GainNode {
  const master = context.createGain();
  const compressor = context.createDynamicsCompressor();

  master.gain.setValueAtTime(Math.max(0.1, Math.min(1, volume)), context.currentTime);
  compressor.threshold.setValueAtTime(-20, context.currentTime);
  compressor.knee.setValueAtTime(18, context.currentTime);
  compressor.ratio.setValueAtTime(5, context.currentTime);
  compressor.attack.setValueAtTime(0.003, context.currentTime);
  compressor.release.setValueAtTime(0.25, context.currentTime);

  master.connect(compressor);
  compressor.connect(context.destination);
  return master;
}

export function scheduleAudibleTone({
  context,
  output,
  midi,
  voice,
  start,
  duration,
  accent = 1,
}: {
  context: AudioContext;
  output: AudioNode;
  midi: number;
  voice: OscillatorType;
  start: number;
  duration: number;
  accent?: number;
}): OscillatorNode[] {
  const audibleNote = audibleMidi(midi);
  const frequency = 440 * 2 ** ((audibleNote - 69) / 12);
  const safeDuration = Math.max(0.06, duration);
  const peak = Math.min(0.22, 0.13 * Math.max(0.55, accent));
  const oscillators: OscillatorNode[] = [];

  // The octave layer makes low executable notes audible on phone speakers while
  // retaining the original interval contour. It is only a playback rendering;
  // exported MIDI and policy semantics are unchanged.
  for (const [frequencyRatio, layerGain] of [[1, 1], [2, 0.36]] as const) {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const filter = context.createBiquadFilter();

    oscillator.type = voice;
    oscillator.frequency.setValueAtTime(frequency * frequencyRatio, start);
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(frequencyRatio === 1 ? 4200 : 5200, start);
    filter.Q.setValueAtTime(0.45, start);

    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak * layerGain), start + 0.014);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + safeDuration * 0.92);

    oscillator.connect(filter);
    filter.connect(gain);
    gain.connect(output);
    oscillator.start(start);
    oscillator.stop(start + safeDuration);
    oscillators.push(oscillator);
  }

  return oscillators;
}
