export type MerzatoValue = bigint | number | string | boolean | null | undefined;

export interface RegisterOperand {
  type: "register";
  index: number;
}

export interface Instruction {
  op: string;
  args: Array<MerzatoValue | RegisterOperand>;
  line?: number;
  artOrder?: number;
}

export interface Program {
  instructions: readonly Instruction[];
  labels: Readonly<Record<string, number>>;
  entry: number;
  sourceType: string;
  filename?: string;
  score?: ReadonlyArray<{order: number; note: number}>;
}

export function assemble(source: string, options?: {filename?: string}): Program;
