import {describe, expect, it} from "vitest";

import {
  buildVelatoPlaybackEvents,
  encodeVelatoMidi,
  parseVelatoInstructions,
  VELATO_SHOWCASE_PROGRAMS,
} from "./velatoShowcase";

function ascii(bytes: Uint8Array, start: number, length: number): string {
  return String.fromCharCode(...bytes.slice(start, start + length));
}

describe("Velato showcase", () => {
  it("contains five distinct functional programs", () => {
    expect(VELATO_SHOWCASE_PROGRAMS).toHaveLength(5);
    expect(new Set(VELATO_SHOWCASE_PROGRAMS.map(program => program.id)).size).toBe(5);
    expect(new Set(VELATO_SHOWCASE_PROGRAMS.map(program => program.route)).size).toBe(5);
  });

  it.each(VELATO_SHOWCASE_PROGRAMS)("parses and sonifies $title", program => {
    const instructions = parseVelatoInstructions(program.source);
    const events = buildVelatoPlaybackEvents(program);

    expect(instructions.length).toBeGreaterThan(40);
    expect(events).toHaveLength(instructions.length);
    expect(events.at(-1)?.operation).toBe("HALT");
    expect(events.every(event => event.bank >= 0 && event.bank <= 3)).toBe(true);
    expect(events.every(event => event.midi >= 0 && event.midi <= 127)).toBe(true);
    expect(events.every(event => event.noteName.length >= 2)).toBe(true);
    expect(program.source).toContain("STORE_SCORE");
    expect(program.source).toContain("STORE_SEVERITY");
    expect(program.source).toContain("STORE_ROUTE");
    expect(program.source).toContain("STORE_SUPPRESS");
  });

  it.each(VELATO_SHOWCASE_PROGRAMS)("exports executable MIDI for $title", program => {
    const midi = encodeVelatoMidi(program);

    expect(ascii(midi, 0, 4)).toBe("MThd");
    expect(ascii(midi, 14, 4)).toBe("MTrk");
    expect(midi.at(-4)).toBe(0x00);
    expect(midi.at(-3)).toBe(0xff);
    expect(midi.at(-2)).toBe(0x2f);
    expect(midi.at(-1)).toBe(0x00);
    expect(midi.length).toBeGreaterThan(300);
  });

  it("preserves the operand-bearing MIDI velocities", () => {
    const privateer = VELATO_SHOWCASE_PROGRAMS[0];
    const events = buildVelatoPlaybackEvents(privateer);
    const firstInput = events.find(event => event.operation === "LOAD_INPUT");
    const firstConstant = events.find(event => event.operation === "PUSH_CONST");

    expect(firstInput?.operand).toBe("watchlist_match");
    expect(firstInput?.velocity).toBe(8);
    expect(firstConstant?.operand).toBe("35");
    expect(firstConstant?.velocity).toBe(36);
  });
});
