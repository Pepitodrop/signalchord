import {describe, expect, it} from "vitest";

import {
  compileMerzatoArtwork,
  DEFAULT_MERZATO_ARTWORK,
  merzatoErrorInfo,
  runMerzatoAssembly,
  runMerzatoArtwork,
} from "./merzatoStudio";

describe("Merzato Policy Studio", () => {
  it("executes bounded Merzato Assembly and exposes deterministic state", () => {
    const result = runMerzatoAssembly(`.entry main
main:
  push 20
  push 22
  add
  dup
  outn
  store r0
  halt`);

    expect(result.sourceType).toBe("assembly");
    expect(result.output).toBe("42");
    expect(result.halted).toBe(true);
    expect(result.registers[0]).toBe("42");
    expect(result.instructions.map(instruction => instruction.op)).toEqual([
      "PUSH", "PUSH", "ADD", "DUP", "OUTN", "STORE", "HALT",
    ]);
  });

  it("fails closed when a program exceeds its step budget", () => {
    try {
      runMerzatoAssembly(`.entry loop
loop:
  jmp loop`, {maxSteps: 25});
      throw new Error("expected resource limit");
    } catch (error) {
      const details = merzatoErrorInfo(error);
      expect(details.code).toBe("RESOURCE_LIMIT");
      expect(details.message).toContain("Step limit exceeded (25)");
    }
  });

  it("compiles Piet colour transitions and MIDI notes into executable Merzato", () => {
    const compiled = compileMerzatoArtwork(DEFAULT_MERZATO_ARTWORK);
    const result = runMerzatoArtwork(DEFAULT_MERZATO_ARTWORK);

    expect(compiled.assembly).toContain("push 42");
    expect(compiled.assembly).toContain("outn");
    expect(compiled.score).toEqual([
      {order: 0, note: 60},
      {order: 1, note: 64},
      {order: 2, note: 71},
    ]);
    expect(result.sourceType).toBe("svg-art");
    expect(result.output).toBe("42");
    expect(result.compiledAssembly).toBe(compiled.assembly);
  });

  it("rejects executable XML entity declarations", () => {
    expect(() => runMerzatoArtwork(`<!DOCTYPE svg [<!ENTITY x "42">]>
<svg><rect data-order="0" fill="#FFC0C0"/><rect data-order="1" fill="#FF0000"/></svg>`))
      .toThrow("DOCTYPE and ENTITY are not allowed");
  });
});
