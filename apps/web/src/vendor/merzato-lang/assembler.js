import { MerzatoSyntaxError } from './errors.js';
import { INSTRUCTION_SIGNATURES, validateProgram } from './validator.js';

function stripComment(line) {
  let quote = null;
  let escaped = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (char === ';') return line.slice(0, i);
  }
  return line;
}

function tokenize(line, lineNumber) {
  const tokens = [];
  let index = 0;

  while (index < line.length) {
    while (index < line.length && /[\s,]/.test(line[index])) index += 1;
    if (index >= line.length) break;

    const start = index;
    const quote = line[index] === '"' || line[index] === "'" ? line[index++] : null;
    let value = quote ?? '';
    let escaped = false;

    if (quote) {
      while (index < line.length) {
        const char = line[index++];
        value += char;
        if (escaped) {
          escaped = false;
          continue;
        }
        if (char === '\\') {
          escaped = true;
          continue;
        }
        if (char === quote) break;
      }
      if (!value.endsWith(quote) || value.length === 1) {
        throw new MerzatoSyntaxError(`Unterminated string on line ${lineNumber}`, {
          code: 'UNTERMINATED_STRING',
          line: lineNumber,
          column: start + 1
        });
      }
    } else {
      while (index < line.length && !/[\s,]/.test(line[index])) {
        value += line[index++];
      }
    }

    tokens.push(value);
  }

  return tokens;
}

function decodeSingleQuoted(token, lineNumber) {
  const inner = token.slice(1, -1);
  let result = '';
  for (let index = 0; index < inner.length; index += 1) {
    const char = inner[index];
    if (char !== '\\') {
      result += char;
      continue;
    }
    if (index + 1 >= inner.length) {
      throw new MerzatoSyntaxError(`Invalid escape sequence on line ${lineNumber}`, {
        code: 'INVALID_STRING',
        line: lineNumber
      });
    }
    const escaped = inner[++index];
    const replacements = { n: '\n', r: '\r', t: '\t', "'": "'", '"': '"', '\\': '\\', '0': '\0' };
    if (Object.hasOwn(replacements, escaped)) {
      result += replacements[escaped];
      continue;
    }
    if (escaped === 'u') {
      const digits = inner.slice(index + 1, index + 5);
      if (!/^[0-9a-fA-F]{4}$/.test(digits)) {
        throw new MerzatoSyntaxError(`Invalid Unicode escape on line ${lineNumber}`, {
          code: 'INVALID_STRING',
          line: lineNumber
        });
      }
      result += String.fromCharCode(Number.parseInt(digits, 16));
      index += 4;
      continue;
    }
    throw new MerzatoSyntaxError(`Unknown escape \\${escaped} on line ${lineNumber}`, {
      code: 'INVALID_STRING',
      line: lineNumber
    });
  }
  return result;
}

function parseString(token, lineNumber) {
  if (token.startsWith('"')) {
    try {
      return JSON.parse(token);
    } catch (error) {
      throw new MerzatoSyntaxError(`Invalid string on line ${lineNumber}: ${error.message}`, {
        code: 'INVALID_STRING',
        line: lineNumber,
        cause: error
      });
    }
  }
  return decodeSingleQuoted(token, lineNumber);
}

function parseLiteral(token, lineNumber) {
  if (/^r(?:[0-9]|1[0-5])$/i.test(token)) {
    return { matched: true, value: { type: 'register', index: Number(token.slice(1)) } };
  }
  if (/^r\d+$/i.test(token)) {
    throw new MerzatoSyntaxError(`Register '${token}' is outside r0-r15 on line ${lineNumber}`, {
      code: 'INVALID_REGISTER',
      line: lineNumber
    });
  }
  if (/^[+-]?\d+$/.test(token)) return { matched: true, value: BigInt(token) };
  if ((token.startsWith('"') && token.endsWith('"')) ||
      (token.startsWith("'") && token.endsWith("'"))) {
    return { matched: true, value: parseString(token, lineNumber) };
  }
  return { matched: false, value: undefined };
}

function cloneConstant(value) {
  return value && typeof value === 'object' && value.type === 'register'
    ? { type: 'register', index: value.index }
    : value;
}

function parseOperand(token, lineNumber, constants) {
  if (token.startsWith('$')) {
    const match = token.match(/^\$([A-Za-z_][\w.-]*)$/);
    if (!match) {
      throw new MerzatoSyntaxError(`Invalid constant reference '${token}' on line ${lineNumber}`, {
        code: 'INVALID_CONSTANT',
        line: lineNumber
      });
    }
    const name = match[1];
    if (!Object.hasOwn(constants, name)) {
      throw new MerzatoSyntaxError(`Unknown constant '${name}' on line ${lineNumber}`, {
        code: 'UNKNOWN_CONSTANT',
        line: lineNumber
      });
    }
    return cloneConstant(constants[name]);
  }

  const literal = parseLiteral(token, lineNumber);
  return literal.matched ? literal.value : token;
}

function collectConstants(lines) {
  const constants = Object.create(null);

  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber += 1) {
    const line = stripComment(lines[lineNumber - 1]).trim();
    if (!line.startsWith('.')) continue;

    const directive = tokenize(line, lineNumber);
    if (directive[0]?.toLowerCase() !== '.const') continue;
    if (directive.length !== 3) {
      throw new MerzatoSyntaxError(`.const expects a name and one literal on line ${lineNumber}`, {
        code: 'INVALID_DIRECTIVE',
        line: lineNumber
      });
    }

    const name = directive[1];
    if (!/^[A-Za-z_][\w.-]*$/.test(name)) {
      throw new MerzatoSyntaxError(`Invalid constant name '${name}' on line ${lineNumber}`, {
        code: 'INVALID_CONSTANT',
        line: lineNumber
      });
    }
    if (Object.hasOwn(constants, name)) {
      throw new MerzatoSyntaxError(`Duplicate constant '${name}' on line ${lineNumber}`, {
        code: 'DUPLICATE_CONSTANT',
        line: lineNumber
      });
    }

    const literal = parseLiteral(directive[2], lineNumber);
    if (!literal.matched) {
      throw new MerzatoSyntaxError(
        `.const '${name}' must contain an integer, register, or quoted string literal on line ${lineNumber}`,
        { code: 'INVALID_CONSTANT', line: lineNumber }
      );
    }
    constants[name] = literal.value;
  }

  return constants;
}

export function assemble(source, { filename = '<memory>' } = {}) {
  if (typeof source !== 'string') {
    throw new TypeError('Assembly source must be a string');
  }

  const instructions = [];
  const labels = Object.create(null);
  let entryLabel = null;

  const lines = source.split(/\r?\n/);
  const constants = collectConstants(lines);

  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber += 1) {
    let line = stripComment(lines[lineNumber - 1]).trim();
    if (!line) continue;

    if (line.startsWith('.')) {
      const directive = tokenize(line, lineNumber);
      const directiveName = directive[0]?.toLowerCase();
      if (directiveName === '.const') continue;
      if (directiveName !== '.entry') {
        throw new MerzatoSyntaxError(`Unknown directive '${directive[0]}' on line ${lineNumber}`, {
          code: 'UNKNOWN_DIRECTIVE',
          line: lineNumber
        });
      }
      if (directive.length !== 2) {
        throw new MerzatoSyntaxError(`.entry expects exactly one label on line ${lineNumber}`, {
          code: 'INVALID_DIRECTIVE',
          line: lineNumber
        });
      }
      if (entryLabel !== null) {
        throw new MerzatoSyntaxError(`Duplicate .entry directive on line ${lineNumber}`, {
          code: 'DUPLICATE_ENTRY',
          line: lineNumber
        });
      }
      entryLabel = directive[1];
      continue;
    }

    const labelMatch = line.match(/^([A-Za-z_][\w.-]*):/);
    if (labelMatch) {
      const label = labelMatch[1];
      if (Object.hasOwn(labels, label)) {
        throw new MerzatoSyntaxError(`Duplicate label '${label}' on line ${lineNumber}`, {
          code: 'DUPLICATE_LABEL',
          line: lineNumber
        });
      }
      labels[label] = instructions.length;
      line = line.slice(labelMatch[0].length).trim();
      if (!line) continue;
    }

    const tokens = tokenize(line, lineNumber);
    if (tokens.length === 0) continue;
    let op = tokens.shift().toUpperCase();
    if (op === 'MERZ') op = 'SYS';
    if (!Object.hasOwn(INSTRUCTION_SIGNATURES, op)) {
      throw new MerzatoSyntaxError(`Unknown instruction '${op}' on line ${lineNumber}`, {
        code: 'UNKNOWN_OPCODE',
        line: lineNumber
      });
    }

    instructions.push({
      op,
      args: tokens.map(token => parseOperand(token, lineNumber, constants)),
      line: lineNumber
    });
  }

  const entry = entryLabel === null ? 0 : labels[entryLabel];
  if (entryLabel !== null && entry === undefined) {
    throw new MerzatoSyntaxError(`Unknown entry label '${entryLabel}'`, {
      code: 'UNKNOWN_ENTRY'
    });
  }

  const program = {
    instructions,
    labels,
    entry,
    sourceType: 'assembly',
    filename
  };
  return validateProgram(program, { freeze: true });
}
