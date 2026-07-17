import {assemble} from "./vendor/merzato-lang/assembler.js";
import type {
  Instruction,
  MerzatoValue,
  Program,
  RegisterOperand,
} from "./vendor/merzato-lang/assembler.js";

export const MERZATO_UPSTREAM = {
  repository: "https://github.com/Pepitodrop/merzato-lang",
  version: "1.0.1",
  commit: "d555a1ebdeb45fdbb84b6df7124c811209846059",
} as const;

export const DEFAULT_MERZATO_ASSEMBLY = `.entry main

main:
  push "SignalChord route: "
  push 7
  tostr
  concat
  merz "THE CRITIC SAYS"
  push 7
  store r0
  halt`;

export const DEFAULT_MERZATO_ARTWORK = `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="120" viewBox="0 0 360 120">
  <rect data-order="0" data-value="42" data-note="60" fill="#FFC0C0" x="0" y="0" width="120" height="120" />
  <rect data-order="1" data-note="64" fill="#FF0000" x="120" y="0" width="120" height="120" />
  <rect data-order="2" data-note="71" fill="#C000C0" x="240" y="0" width="120" height="120" />
</svg>`;

export type MerzatoErrorInfo = {
  message: string;
  code: string;
  line?: number;
  artOrder?: number;
  pc?: number;
};

export type MerzatoInstructionView = {
  pc: number;
  op: string;
  operands: string;
  sourceLine?: number;
};

export type MerzatoRunReport = {
  sourceType: "assembly" | "svg-art";
  output: string;
  steps: number;
  halted: boolean;
  pc: number;
  stack: string[];
  registers: string[];
  heapSize: number;
  instructions: MerzatoInstructionView[];
  compiledAssembly?: string;
  score?: Array<{order: number; note: number}>;
};

type RuntimeLimits = {
  maxSteps: number;
  maxStackDepth: number;
  maxCallDepth: number;
  maxHeapCells: number;
  maxStringLength: number;
};

const DEFAULT_LIMITS: RuntimeLimits = {
  maxSteps: 10_000,
  maxStackDepth: 512,
  maxCallDepth: 128,
  maxHeapCells: 256,
  maxStringLength: 20_000,
};

const PALETTE = new Map<string, readonly [number, number]>([
  ["#FFC0C0", [0, 0]], ["#FFFFC0", [1, 0]], ["#C0FFC0", [2, 0]],
  ["#C0FFFF", [3, 0]], ["#C0C0FF", [4, 0]], ["#FFC0FF", [5, 0]],
  ["#FF0000", [0, 1]], ["#FFFF00", [1, 1]], ["#00FF00", [2, 1]],
  ["#00FFFF", [3, 1]], ["#0000FF", [4, 1]], ["#FF00FF", [5, 1]],
  ["#C00000", [0, 2]], ["#C0C000", [1, 2]], ["#00C000", [2, 2]],
  ["#00C0C0", [3, 2]], ["#0000C0", [4, 2]], ["#C000C0", [5, 2]],
]);

const TRANSITIONS = [
  ["NOP", "PUSH", "POP"],
  ["ADD", "SUB", "MUL"],
  ["DIV", "MOD", "NOT"],
  ["CMPGT", "JMP", "JZ"],
  ["DUP", "LOAD", "STORE"],
  ["SYS", "OUTN", "OUTC"],
] as const;

function isRegister(value: MerzatoValue | RegisterOperand): value is RegisterOperand {
  return Boolean(value && typeof value === "object" && "type" in value && value.type === "register");
}

function valueText(value: MerzatoValue | RegisterOperand): string {
  if (isRegister(value)) return `r${value.index}`;
  if (typeof value === "bigint") return value.toString();
  if (typeof value === "string") return JSON.stringify(value);
  return String(value);
}

function instructionViews(program: Program): MerzatoInstructionView[] {
  return program.instructions.map((instruction, pc) => ({
    pc,
    op: instruction.op,
    operands: instruction.args.map(valueText).join(" "),
    sourceLine: instruction.line,
  }));
}

function normalizeMerzName(value: unknown): string {
  return String(value).trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function asError(error: unknown): Error & Partial<MerzatoErrorInfo> {
  return error instanceof Error ? error : new Error(String(error));
}

export function merzatoErrorInfo(error: unknown): MerzatoErrorInfo {
  const value = asError(error);
  return {
    message: value.message,
    code: typeof value.code === "string" ? value.code : "MERZATO_ERROR",
    line: typeof value.line === "number" ? value.line : undefined,
    artOrder: typeof value.artOrder === "number" ? value.artOrder : undefined,
    pc: typeof value.pc === "number" ? value.pc : undefined,
  };
}

class RestrictedMerzatoVM {
  private readonly registers: MerzatoValue[] = Array.from({length: 16}, () => 0n);
  private readonly stack: MerzatoValue[] = [];
  private readonly callStack: number[] = [];
  private readonly heap = new Map<string, MerzatoValue>();
  private readonly limits: RuntimeLimits;
  private pc: number;
  private halted = false;
  private output = "";
  private steps = 0;

  constructor(private readonly program: Program, limits: Partial<RuntimeLimits> = {}) {
    this.limits = {...DEFAULT_LIMITS, ...limits};
    this.pc = program.entry;
  }

  private fail(message: string, code: string, instruction?: Instruction): never {
    const error = new Error(message) as Error & Partial<MerzatoErrorInfo>;
    error.code = code;
    error.pc = this.pc;
    error.line = instruction?.line;
    throw error;
  }

  private checkValue(value: MerzatoValue): MerzatoValue {
    if (typeof value === "string" && value.length > this.limits.maxStringLength) {
      return this.fail(`String limit exceeded (${this.limits.maxStringLength})`, "RESOURCE_LIMIT");
    }
    return value;
  }

  private push(value: MerzatoValue): void {
    if (this.stack.length >= this.limits.maxStackDepth) {
      this.fail(`Stack limit exceeded (${this.limits.maxStackDepth})`, "RESOURCE_LIMIT");
    }
    this.stack.push(this.checkValue(value));
  }

  private pop(): MerzatoValue {
    if (this.stack.length === 0) this.fail("Stack underflow", "STACK_UNDERFLOW");
    return this.stack.pop() as MerzatoValue;
  }

  private peek(): MerzatoValue {
    if (this.stack.length === 0) this.fail("Stack underflow", "STACK_UNDERFLOW");
    return this.stack[this.stack.length - 1];
  }

  private integer(value: MerzatoValue): bigint {
    if (typeof value === "bigint") return value;
    if (typeof value === "number" && Number.isSafeInteger(value)) return BigInt(value);
    if (typeof value === "string" && /^[+-]?\d+$/.test(value)) return BigInt(value);
    return this.fail(`Expected an integer, got ${String(value)}`, "TYPE_ERROR");
  }

  private zero(value: MerzatoValue): boolean {
    return typeof value === "bigint"
      ? value === 0n
      : value === 0 || value === false || value === "" || value === null || value === undefined;
  }

  private register(value: MerzatoValue | RegisterOperand): number {
    if (!isRegister(value) || value.index < 0 || value.index >= this.registers.length) {
      return this.fail("Expected register r0-r15", "INVALID_REGISTER");
    }
    return value.index;
  }

  private target(value: MerzatoValue | RegisterOperand): number {
    let target: number | undefined;
    if (typeof value === "bigint") target = Number(value);
    else if (typeof value === "number") target = value;
    else if (typeof value === "string") target = this.program.labels[value];
    if (!Number.isSafeInteger(target) || (target as number) < 0 || (target as number) > this.program.instructions.length) {
      return this.fail(`Invalid jump target ${String(value)}`, "INVALID_TARGET");
    }
    return target as number;
  }

  private binary(operation: (left: bigint, right: bigint) => bigint): void {
    const right = this.integer(this.pop());
    const left = this.integer(this.pop());
    this.push(operation(left, right));
  }

  private appendCharacter(value: MerzatoValue): void {
    const codePoint = Number(this.integer(value));
    if (!Number.isSafeInteger(codePoint) || codePoint < 0 || codePoint > 0x10ffff ||
        (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
      this.fail(`Invalid Unicode scalar value ${String(value)}`, "TYPE_ERROR");
    }
    this.output += String.fromCodePoint(codePoint);
  }

  private syscall(name: unknown): void {
    switch (normalizeMerzName(name)) {
      case "THE_CRITIC_SAYS":
        this.output += `${String(this.pop())}\n`;
        return;
      case "THE_PERFORMANCE_IS_OVER":
        this.halted = true;
        return;
      default:
        this.fail(`MerzScript phrase '${String(name)}' is not enabled in SignalChord`, "UNSUPPORTED_SYSCALL");
    }
  }

  private step(): void {
    const instruction = this.program.instructions[this.pc];
    if (!instruction) {
      this.halted = true;
      return;
    }
    this.pc += 1;
    const [operand] = instruction.args;

    switch (instruction.op) {
      case "NOP": break;
      case "PUSH": this.push(operand as MerzatoValue); break;
      case "POP": this.pop(); break;
      case "DUP": this.push(this.peek()); break;
      case "SWAP": {
        const right = this.pop();
        const left = this.pop();
        this.push(right);
        this.push(left);
        break;
      }
      case "ADD": this.binary((left, right) => left + right); break;
      case "SUB": this.binary((left, right) => left - right); break;
      case "MUL": this.binary((left, right) => left * right); break;
      case "DIV": this.binary((left, right) => {
        if (right === 0n) this.fail("Division by zero", "DIVISION_BY_ZERO", instruction);
        return left / right;
      }); break;
      case "MOD": this.binary((left, right) => {
        if (right === 0n) this.fail("Modulo by zero", "DIVISION_BY_ZERO", instruction);
        const result = left % right;
        return result < 0n ? result + (right < 0n ? -right : right) : result;
      }); break;
      case "NOT": this.push(this.zero(this.pop()) ? 1n : 0n); break;
      case "CMPGT": this.binary((left, right) => left > right ? 1n : 0n); break;
      case "LOAD": this.push(this.registers[this.register(operand)]); break;
      case "STORE": this.registers[this.register(operand)] = this.checkValue(this.pop()); break;
      case "HLOAD": this.push(this.heap.get(this.integer(this.pop()).toString()) ?? 0n); break;
      case "HSTORE": {
        const address = this.integer(this.pop()).toString();
        const value = this.checkValue(this.pop());
        if (!this.heap.has(address) && this.heap.size >= this.limits.maxHeapCells) {
          this.fail(`Heap limit exceeded (${this.limits.maxHeapCells})`, "RESOURCE_LIMIT", instruction);
        }
        this.heap.set(address, value);
        break;
      }
      case "JMP": this.pc = this.target(operand); break;
      case "JZ": if (this.zero(this.pop())) this.pc = this.target(operand); break;
      case "JNZ": if (!this.zero(this.pop())) this.pc = this.target(operand); break;
      case "CALL":
        if (this.callStack.length >= this.limits.maxCallDepth) {
          this.fail(`Call-stack limit exceeded (${this.limits.maxCallDepth})`, "RESOURCE_LIMIT", instruction);
        }
        this.callStack.push(this.pc);
        this.pc = this.target(operand);
        break;
      case "RET": this.pc = this.callStack.pop() ?? this.program.instructions.length; break;
      case "TOSTR": this.push(String(this.pop())); break;
      case "CONCAT": {
        const right = String(this.pop());
        const left = String(this.pop());
        this.push(left + right);
        break;
      }
      case "OUTN": this.output += this.integer(this.pop()).toString(); break;
      case "OUTC": this.appendCharacter(this.pop()); break;
      case "SYS": this.syscall(operand); break;
      case "HALT": this.halted = true; break;
      default: this.fail(`Unsupported opcode ${instruction.op}`, "UNKNOWN_OPCODE", instruction);
    }
  }

  run(): Omit<MerzatoRunReport, "sourceType" | "instructions"> {
    while (!this.halted) {
      if (this.steps >= this.limits.maxSteps) {
        this.fail(`Step limit exceeded (${this.limits.maxSteps})`, "RESOURCE_LIMIT");
      }
      this.step();
      this.steps += 1;
    }

    return {
      output: this.output,
      steps: this.steps,
      halted: this.halted,
      pc: this.pc,
      stack: this.stack.map(valueText),
      registers: this.registers.map(valueText),
      heapSize: this.heap.size,
    };
  }
}

function executeProgram(program: Program, sourceType: "assembly" | "svg-art", limits?: Partial<RuntimeLimits>): MerzatoRunReport {
  return {
    sourceType,
    instructions: instructionViews(program),
    ...new RestrictedMerzatoVM(program, limits).run(),
  };
}

export function runMerzatoAssembly(source: string, limits?: Partial<RuntimeLimits>): MerzatoRunReport {
  const program = assemble(source, {filename: "signalchord-policy.mza"});
  return executeProgram(program, "assembly", limits);
}

type ArtBlock = {
  attrs: Record<string, string>;
  order: number;
  colour: readonly [number, number];
  note: number;
};

function extractTags(source: string, name: string): string[] {
  const expression = new RegExp(`<${name}\\b[^>]*>`, "gi");
  return source.match(expression) ?? [];
}

function parseAttributes(tag: string): Record<string, string> {
  const result: Record<string, string> = {};
  const expression = /([:\w.-]+)\s*=\s*("([^"]*)"|'([^']*)')/g;
  for (const match of tag.matchAll(expression)) {
    if (result[match[1]] !== undefined) throw new Error(`Duplicate SVG attribute '${match[1]}'`);
    result[match[1]] = match[3] ?? match[4] ?? "";
  }
  return result;
}

function artInteger(raw: string | undefined, label: string, order: number): bigint {
  if (raw === undefined || !/^[+-]?\d+$/.test(raw)) {
    throw new Error(`Art block ${order} has invalid ${label}`);
  }
  return BigInt(raw);
}

function artValue(block: ArtBlock): bigint {
  if (block.attrs["data-value"] !== undefined) return artInteger(block.attrs["data-value"], "data-value", block.order);
  if (block.attrs["data-codels"] !== undefined) return artInteger(block.attrs["data-codels"], "data-codels", block.order);
  const width = Number(block.attrs.width ?? 1);
  const height = Number(block.attrs.height ?? 1);
  const codelSize = Number(block.attrs["data-codel-size"] ?? 1);
  if (![width, height, codelSize].every(value => Number.isFinite(value) && value > 0)) {
    throw new Error(`Art block ${block.order} has invalid dimensions`);
  }
  return BigInt(Math.max(1, Math.round((width / codelSize) * (height / codelSize))));
}

function assemblyLiteral(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new Error("Merzato artwork arguments must use safe integers");
    return String(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean" || value === null) return JSON.stringify(value);
  throw new Error("Merzato artwork arguments must be strings, booleans, null, or integers");
}

export function compileMerzatoArtwork(svgSource: string): {
  program: Program;
  assembly: string;
  score: Array<{order: number; note: number}>;
} {
  if (new TextEncoder().encode(svgSource).byteLength > 250_000) throw new Error("SVG source exceeds 250000 bytes");
  if (/<!DOCTYPE|<!ENTITY/i.test(svgSource)) throw new Error("DOCTYPE and ENTITY are not allowed in Merzato artwork");
  if (extractTags(svgSource, "svg").length === 0) throw new Error("Merzato artwork needs an SVG root");

  const blocks = extractTags(svgSource, "rect")
    .map(parseAttributes)
    .filter(attrs => attrs["data-order"] !== undefined)
    .map(attrs => {
      const order = Number(attrs["data-order"]);
      const colour = PALETTE.get(String(attrs.fill ?? "").toUpperCase());
      const note = Number(attrs["data-note"] ?? 60);
      if (!Number.isSafeInteger(order) || order < 0) throw new Error(`Invalid data-order '${attrs["data-order"]}'`);
      if (!colour) throw new Error(`Art block ${order} uses an unsupported Piet colour`);
      if (!Number.isInteger(note) || note < 0 || note > 127) throw new Error(`Art block ${order} has an invalid MIDI note`);
      return {attrs, order, colour, note};
    })
    .sort((left, right) => left.order - right.order);

  if (blocks.length < 2) throw new Error("A Merzato artwork needs at least two ordered colour blocks");
  if (blocks.length > 256) throw new Error("Merzato artwork exceeds 256 executable blocks");
  if (new Set(blocks.map(block => block.order)).size !== blocks.length) throw new Error("Merzato artwork has duplicate data-order values");

  const lines: string[] = [".entry main", "", "main:"];
  for (let index = 0; index < blocks.length - 1; index += 1) {
    const source = blocks[index];
    const destination = blocks[index + 1];
    const label = destination.attrs["data-label"];
    if (label) {
      if (!/^[A-Za-z_][\w.-]*$/.test(label)) throw new Error(`Art block ${destination.order} has an invalid label`);
      lines.push(`${label}:`);
    }

    const hueDelta = (destination.colour[0] - source.colour[0] + 6) % 6;
    const lightDelta = (destination.colour[1] - source.colour[1] + 3) % 3;
    const op = TRANSITIONS[hueDelta][lightDelta];

    if (op === "PUSH") {
      lines.push(`  push ${artValue(source).toString()}`);
    } else if (op === "LOAD" || op === "STORE") {
      const register = ((destination.note - source.note) % 16 + 16) % 16;
      lines.push(`  ${op.toLowerCase()} r${register}`);
    } else if (op === "JMP" || op === "JZ") {
      const target = destination.attrs["data-target"];
      if (!target) throw new Error(`${op} transition into art block ${destination.order} needs data-target`);
      lines.push(`  ${op.toLowerCase()} ${target}`);
    } else if (op === "SYS") {
      const args = destination.attrs["data-args"] ? JSON.parse(destination.attrs["data-args"]) as unknown : [];
      if (!Array.isArray(args)) throw new Error(`Art block ${destination.order} data-args must be an array`);
      for (const argument of args) lines.push(`  push ${assemblyLiteral(argument)}`);
      const phrase = destination.attrs["data-merz"];
      if (!phrase) throw new Error(`SYS transition into art block ${destination.order} needs data-merz`);
      lines.push(`  merz ${JSON.stringify(phrase)}`);
      if (destination.attrs["data-store"]) lines.push(`  store ${destination.attrs["data-store"]}`);
    } else {
      lines.push(`  ${op.toLowerCase()}`);
    }
  }
  lines.push("  halt");

  const assembly = lines.join("\n");
  return {
    program: assemble(assembly, {filename: "signalchord-artwork.mza"}),
    assembly,
    score: blocks.map(block => ({order: block.order, note: block.note})),
  };
}

export function runMerzatoArtwork(svgSource: string, limits?: Partial<RuntimeLimits>): MerzatoRunReport {
  const compiled = compileMerzatoArtwork(svgSource);
  return {
    ...executeProgram(compiled.program, "svg-art", limits),
    compiledAssembly: compiled.assembly,
    score: compiled.score,
  };
}
