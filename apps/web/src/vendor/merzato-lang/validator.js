import { MerzatoValidationError } from './errors.js';

export const REGISTER_COUNT = 16;

const SIGNATURES = {
  NOP: [],
  PUSH: ['value'],
  POP: [],
  DUP: [],
  SWAP: [],
  ADD: [],
  SUB: [],
  MUL: [],
  DIV: [],
  MOD: [],
  NOT: [],
  CMPGT: [],
  LOAD: ['register'],
  STORE: ['register'],
  HLOAD: [],
  HSTORE: [],
  JMP: ['target'],
  JZ: ['target'],
  JNZ: ['target'],
  CALL: ['target'],
  RET: [],
  TOSTR: [],
  CONCAT: [],
  OUTN: [],
  OUTC: [],
  SYS: ['phrase'],
  HALT: []
};

for (const signature of Object.values(SIGNATURES)) Object.freeze(signature);
export const INSTRUCTION_SIGNATURES = Object.freeze(SIGNATURES);
export const VALID_OPS = new Set(Object.keys(INSTRUCTION_SIGNATURES));

export function isRegister(value) {
  return Boolean(
    value &&
    typeof value === 'object' &&
    value.type === 'register' &&
    Number.isInteger(value.index) &&
    value.index >= 0 &&
    value.index < REGISTER_COUNT
  );
}

function fail(message, instruction, index, code = 'INVALID_PROGRAM') {
  throw new MerzatoValidationError(message, {
    code,
    pc: index,
    line: instruction?.line,
    artOrder: instruction?.artOrder
  });
}

function validateArg(kind, value, program, instruction, index) {
  switch (kind) {
    case 'value':
      if (value === undefined) fail('PUSH requires a value', instruction, index, 'INVALID_OPERAND');
      return;
    case 'register':
      if (!isRegister(value)) fail('Expected register r0-r15', instruction, index, 'INVALID_REGISTER');
      return;
    case 'target': {
      if (typeof value === 'string') {
        if (!Object.hasOwn(program.labels, value)) {
          fail(`Unknown jump target '${value}'`, instruction, index, 'UNKNOWN_LABEL');
        }
        return;
      }
      const numeric = typeof value === 'bigint' ? Number(value) : value;
      if (!Number.isSafeInteger(numeric) || numeric < 0 || numeric > program.instructions.length) {
        fail(`Invalid jump target '${String(value)}'`, instruction, index, 'INVALID_TARGET');
      }
      return;
    }
    case 'phrase':
      if (typeof value !== 'string' || value.trim() === '') {
        fail('SYS/MERZ requires a non-empty string phrase', instruction, index, 'INVALID_SYSCALL');
      }
      return;
    default:
      fail(`Unknown validator operand kind '${kind}'`, instruction, index);
  }
}

function freezeProgram(program) {
  const labels = Object.assign(Object.create(null), program.labels);
  Object.freeze(labels);
  const instructions = program.instructions.map(instruction => Object.freeze({
    ...instruction,
    args: Object.freeze(instruction.args.map(arg =>
      isRegister(arg) ? Object.freeze({ type: 'register', index: arg.index }) : arg
    ))
  }));
  const frozen = { ...program, labels, instructions: Object.freeze(instructions) };
  if (Array.isArray(program.score)) {
    frozen.score = Object.freeze(program.score.map(item => Object.freeze({ ...item })));
  }
  return Object.freeze(frozen);
}

export function validateProgram(program, { freeze = false } = {}) {
  if (!program || typeof program !== 'object') {
    throw new MerzatoValidationError('Program must be an object', { code: 'INVALID_PROGRAM' });
  }
  if (!Array.isArray(program.instructions)) {
    throw new MerzatoValidationError('Program.instructions must be an array', { code: 'INVALID_PROGRAM' });
  }
  if (!program.labels || typeof program.labels !== 'object' || Array.isArray(program.labels)) {
    throw new MerzatoValidationError('Program.labels must be an object', { code: 'INVALID_PROGRAM' });
  }

  for (const [label, target] of Object.entries(program.labels)) {
    if (!/^[A-Za-z_][\w.-]*$/.test(label)) {
      throw new MerzatoValidationError(`Invalid label name '${label}'`, { code: 'INVALID_LABEL' });
    }
    if (!Number.isSafeInteger(target) || target < 0 || target > program.instructions.length) {
      throw new MerzatoValidationError(`Label '${label}' points outside the program`, {
        code: 'INVALID_LABEL',
        label
      });
    }
  }

  const entry = program.entry ?? 0;
  if (!Number.isSafeInteger(entry) || entry < 0 || entry > program.instructions.length) {
    throw new MerzatoValidationError('Program entry is outside the instruction stream', {
      code: 'INVALID_ENTRY'
    });
  }

  program.instructions.forEach((instruction, index) => {
    if (!instruction || typeof instruction !== 'object') {
      fail('Instruction must be an object', instruction, index);
    }
    if (!Object.hasOwn(INSTRUCTION_SIGNATURES, instruction.op)) {
      fail(`Unsupported opcode '${String(instruction.op)}'`, instruction, index, 'UNKNOWN_OPCODE');
    }
    if (!Array.isArray(instruction.args)) {
      fail('Instruction args must be an array', instruction, index, 'INVALID_OPERAND');
    }
    const signature = INSTRUCTION_SIGNATURES[instruction.op];
    if (instruction.args.length !== signature.length) {
      fail(
        `${instruction.op} expects ${signature.length} operand${signature.length === 1 ? '' : 's'}, got ${instruction.args.length}`,
        instruction,
        index,
        'INVALID_ARITY'
      );
    }
    signature.forEach((kind, argIndex) => {
      validateArg(kind, instruction.args[argIndex], program, instruction, index);
    });
  });

  return freeze ? freezeProgram(program) : program;
}
