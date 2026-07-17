export class MerzatoError extends Error {
  constructor(message, { code = 'MERZATO_ERROR', cause, ...details } = {}) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = new.target.name;
    this.code = code;
    Object.assign(this, details);
  }
}

export class MerzatoSyntaxError extends SyntaxError {
  constructor(message, { code = 'SYNTAX_ERROR', cause, line, column, artOrder } = {}) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = 'MerzatoSyntaxError';
    this.code = code;
    if (line !== undefined) this.line = line;
    if (column !== undefined) this.column = column;
    if (artOrder !== undefined) this.artOrder = artOrder;
  }
}

export class MerzatoValidationError extends MerzatoError {
  constructor(message, details = {}) {
    super(message, { code: 'VALIDATION_ERROR', ...details });
  }
}

export class MerzatoRuntimeError extends MerzatoError {
  constructor(message, details = {}) {
    super(message, { code: 'RUNTIME_ERROR', ...details });
  }
}

export class MerzatoResourceError extends MerzatoRuntimeError {
  constructor(message, details = {}) {
    super(message, { code: 'RESOURCE_LIMIT', ...details });
  }
}

export function formatLocation(details = {}) {
  const parts = [];
  if (details.line !== undefined) parts.push(`line ${details.line}`);
  if (details.artOrder !== undefined) parts.push(`art block ${details.artOrder}`);
  if (details.pc !== undefined) parts.push(`pc ${details.pc}`);
  return parts.length === 0 ? '' : ` (${parts.join(', ')})`;
}
