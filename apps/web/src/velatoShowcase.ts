import watchlistPrivateerSource from "../../../velato/programs/watchlist-privateer.vasm?raw";
import cityWaltzSource from "../../../velato/programs/city-waltz.vasm?raw";
import contradictionCanonSource from "../../../velato/programs/contradiction-canon.vasm?raw";
import sourceTrustNocturneSource from "../../../velato/programs/source-trust-nocturne.vasm?raw";
import noveltyRondoSource from "../../../velato/programs/novelty-rondo.vasm?raw";

const INPUTS = [
  "source_trust",
  "corroboration_count",
  "contradiction_count",
  "novelty",
  "entity_relevance",
  "graph_centrality",
  "geographic_relevance",
  "watchlist_match",
  "recency",
  "source_diversity",
] as const;

const INSTRUCTION_BANKS = [
  [
    "HALT",
    "PUSH_CONST",
    "LOAD_INPUT",
    "ADD",
    "SUB",
    "MUL",
    "GT",
    "SELECT",
    "STORE_SCORE",
    "STORE_SEVERITY",
    "STORE_ROUTE",
    "STORE_SUPPRESS",
  ],
  ["MIN", "MAX", "DIV", "MOD", "NEG", "ABS", "CLAMP", "FLOOR", "CEIL", "ROUND", "POW", "SQRT"],
  ["EQ", "NE", "LT", "LTE", "GTE", "AND", "OR", "XOR", "NOT", "IS_ZERO", "BETWEEN", "SIGN"],
  [
    "DUP",
    "SWAP",
    "OVER",
    "DROP",
    "LOAD_LOCAL",
    "STORE_LOCAL",
    "NOP",
    "STACK_DEPTH",
    "LOAD_SCORE",
    "LOAD_SEVERITY",
    "LOAD_ROUTE",
    "LOAD_SUPPRESS",
  ],
] as const;

const OP_ENCODING = new Map<string, {bank: number; interval: number}>();
INSTRUCTION_BANKS.forEach((operations, bank) => {
  operations.forEach((operation, interval) => {
    OP_ENCODING.set(operation, {bank, interval});
  });
});

const NOTE_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

export interface VelatoInstruction {
  operation: string;
  operand?: string;
}

export interface VelatoShowcaseProgram {
  id: string;
  title: string;
  filename: string;
  source: string;
  style: string;
  meter: string;
  tempo: number;
  rootMidi: number;
  route: number;
  purpose: string;
  rhythm: readonly number[];
  accents: readonly number[];
}

export interface VelatoPlaybackEvent {
  operation: string;
  operand?: string;
  bank: number;
  interval: number;
  midi: number;
  noteName: string;
  velocity: number;
  durationBeats: number;
  accent: number;
}

export const VELATO_SHOWCASE_PROGRAMS: readonly VelatoShowcaseProgram[] = [
  {
    id: "watchlist-privateer",
    title: "Watchlist Privateer",
    filename: "watchlist-privateer.mid",
    source: watchlistPrivateerSource,
    style: "Original cinematic seafaring pulse",
    meter: "6/8",
    tempo: 132,
    rootMidi: 50,
    route: 7,
    purpose:
      "Escalates fast-moving, corroborated watchlist stories, discounts contradiction pressure, routes urgent material to queue 7, and suppresses low-trust or heavily contradicted items.",
    rhythm: [0.34, 0.18, 0.18, 0.32, 0.18, 0.18],
    accents: [1.25, 0.72, 0.72, 1.05, 0.72, 0.72],
  },
  {
    id: "city-waltz",
    title: "City Waltz",
    filename: "city-waltz.mid",
    source: cityWaltzSource,
    style: "Original modern German indie-pop waltz",
    meter: "3/4",
    tempo: 104,
    rootMidi: 55,
    route: 4,
    purpose:
      "Prioritizes geographically relevant, diverse and trustworthy stories, routes strong local-impact items to queue 4, and suppresses weakly sourced or insufficiently diverse material.",
    rhythm: [0.34, 0.18, 0.18],
    accents: [1.2, 0.72, 0.72],
  },
  {
    id: "contradiction-canon",
    title: "Contradiction Canon",
    filename: "contradiction-canon.mid",
    source: contradictionCanonSource,
    style: "Original investigation canon",
    meter: "4/4",
    tempo: 118,
    rootMidi: 57,
    route: 5,
    purpose:
      "Detects contradiction-heavy stories with investigation value, combines contradiction, novelty, watchlist and diversity signals, and routes qualifying material to queue 5.",
    rhythm: [0.24, 0.2, 0.24, 0.16],
    accents: [1.08, 0.78, 0.92, 0.72],
  },
  {
    id: "source-trust-nocturne",
    title: "Source Trust Nocturne",
    filename: "source-trust-nocturne.mid",
    source: sourceTrustNocturneSource,
    style: "Original restrained nocturne",
    meter: "4/4",
    tempo: 82,
    rootMidi: 48,
    route: 2,
    purpose:
      "Acts as a source-quality gate, rewards trust, corroboration, diversity and recency, routes highly trusted material to queue 2, and suppresses low-trust or uncorroborated items.",
    rhythm: [0.22, 0.18, 0.18, 0.28],
    accents: [1.02, 0.7, 0.74, 0.88],
  },
  {
    id: "novelty-rondo",
    title: "Novelty Rondo",
    filename: "novelty-rondo.mid",
    source: noveltyRondoSource,
    style: "Original returning discovery motif",
    meter: "4/4",
    tempo: 124,
    rootMidi: 60,
    route: 3,
    purpose:
      "Identifies emerging stories using novelty, recency, entity relevance and graph position, routes strong discoveries to queue 3, and suppresses stale low-novelty noise unless it matches a watchlist.",
    rhythm: [0.26, 0.16, 0.16, 0.22],
    accents: [1.12, 0.72, 0.78, 0.9],
  },
] as const;

export function parseVelatoInstructions(source: string): VelatoInstruction[] {
  return source
    .split(/\r?\n/)
    .map(line => line.replace(/#.*$/, "").trim())
    .filter(Boolean)
    .map(line => {
      const [operation, ...operandParts] = line.split(/\s+/);
      if (!OP_ENCODING.has(operation)) {
        throw new Error(`Unknown Velato operation: ${operation}`);
      }
      return {
        operation,
        operand: operandParts.length ? operandParts.join(" ") : undefined,
      };
    });
}

function operandVelocity(instruction: VelatoInstruction): number {
  if (instruction.operation === "PUSH_CONST") {
    const value = Number(instruction.operand);
    if (!Number.isInteger(value) || value < 0 || value > 126) {
      throw new Error(`PUSH_CONST cannot be encoded in MIDI: ${instruction.operand ?? "missing"}`);
    }
    return value + 1;
  }

  if (instruction.operation === "LOAD_INPUT") {
    const index = INPUTS.indexOf(instruction.operand as (typeof INPUTS)[number]);
    if (index < 0) throw new Error(`Unknown Velato input: ${instruction.operand ?? "missing"}`);
    return index + 1;
  }

  if (instruction.operation === "LOAD_LOCAL" || instruction.operation === "STORE_LOCAL") {
    const value = Number(instruction.operand);
    if (!Number.isInteger(value) || value < 0 || value > 15) {
      throw new Error(`Invalid local register: ${instruction.operand ?? "missing"}`);
    }
    return value + 1;
  }

  return 64;
}

export function midiNoteName(midi: number): string {
  const normalized = Math.max(0, Math.min(127, Math.round(midi)));
  return `${NOTE_NAMES[normalized % 12]}${Math.floor(normalized / 12) - 1}`;
}

export function midiFrequency(midi: number): number {
  return 440 * 2 ** ((midi - 69) / 12);
}

export function buildVelatoPlaybackEvents(program: VelatoShowcaseProgram): VelatoPlaybackEvent[] {
  return parseVelatoInstructions(program.source).map((instruction, index) => {
    const encoding = OP_ENCODING.get(instruction.operation);
    if (!encoding) throw new Error(`Missing encoding for ${instruction.operation}`);
    const midi = program.rootMidi + encoding.interval;
    return {
      ...instruction,
      ...encoding,
      midi,
      noteName: midiNoteName(midi),
      velocity: operandVelocity(instruction),
      durationBeats: program.rhythm[index % program.rhythm.length],
      accent: program.accents[index % program.accents.length],
    };
  });
}

function variableLength(value: number): number[] {
  let buffer = value & 0x7f;
  const output: number[] = [];
  while ((value >>= 7)) {
    buffer <<= 8;
    buffer |= (value & 0x7f) | 0x80;
  }
  while (true) {
    output.push(buffer & 0xff);
    if (buffer & 0x80) buffer >>= 8;
    else break;
  }
  return output;
}

function u16(value: number): number[] {
  return [(value >> 8) & 0xff, value & 0xff];
}

function u32(value: number): number[] {
  return [(value >> 24) & 0xff, (value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function ascii(value: string): number[] {
  return Array.from(value, character => character.charCodeAt(0));
}

export function encodeVelatoMidi(program: VelatoShowcaseProgram): Uint8Array {
  const ticksPerBeat = 480;
  const noteTicks = 120;
  const track: number[] = [];
  const microsecondsPerBeat = Math.round(60_000_000 / program.tempo);

  track.push(0x00, 0xff, 0x51, 0x03, ...u32(microsecondsPerBeat).slice(1));
  track.push(0x00, 0x90, program.rootMidi, 64);
  track.push(...variableLength(noteTicks), 0x80, program.rootMidi, 0);

  for (const event of buildVelatoPlaybackEvents(program)) {
    track.push(0x00, 0x90 | event.bank, event.midi, event.velocity);
    track.push(...variableLength(noteTicks), 0x80 | event.bank, event.midi, 0);
  }

  track.push(0x00, 0xff, 0x2f, 0x00);

  return new Uint8Array([
    ...ascii("MThd"),
    ...u32(6),
    ...u16(0),
    ...u16(1),
    ...u16(ticksPerBeat),
    ...ascii("MTrk"),
    ...u32(track.length),
    ...track,
  ]);
}
