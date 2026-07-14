# SignalChord Velato policy contract

SignalChord implements a constrained, versioned Velato-inspired dialect for auditable alert policies. It preserves the musical root-note/interval model while intentionally not claiming compatibility with every historical Velato interpreter behavior.

## Registers

Inputs are normalized scalar registers named `source_trust`, `corroboration_count`, `contradiction_count`, `novelty`, `entity_relevance`, `graph_centrality`, `geographic_relevance`, `watchlist_match`, `recency` and `source_diversity`.

Outputs are `alert_score` 0–100, `severity_code` 0–9, `routing_code` 0–255 and `suppressed`.

Sixteen local scalar registers (`0`–`15`) are available inside a policy execution. They are initialized to zero and cannot escape the interpreter.

## MIDI encoding

1. The first positive-velocity note defines the root pitch.
2. Each later positive-velocity note selects an interval with `(note - root) mod 12`.
3. MIDI channel selects one of four instruction banks.
4. Velocity encodes constrained operands for constants and register selectors.

### Bank 0 — backwards-compatible core

`HALT`, `PUSH_CONST`, `LOAD_INPUT`, `ADD`, `SUB`, `MUL`, `GT`, `SELECT`, `STORE_SCORE`, `STORE_SEVERITY`, `STORE_ROUTE`, `STORE_SUPPRESS`.

### Bank 1 — safe numeric operations

`MIN`, `MAX`, `DIV`, `MOD`, `NEG`, `ABS`, `CLAMP`, `FLOOR`, `CEIL`, `ROUND`, `POW`, `SQRT`.

### Bank 2 — comparisons and boolean logic

`EQ`, `NE`, `LT`, `LTE`, `GTE`, `AND`, `OR`, `XOR`, `NOT`, `IS_ZERO`, `BETWEEN`, `SIGN`.

### Bank 3 — stack and local state

`DUP`, `SWAP`, `OVER`, `DROP`, `LOAD_LOCAL`, `STORE_LOCAL`, `NOP`, `STACK_DEPTH`, `LOAD_SCORE`, `LOAD_SEVERITY`, `LOAD_ROUTE`, `LOAD_SUPPRESS`.

The capability endpoint is authoritative for the exact interval-to-opcode map of a deployed compiler version.

## Determinism and limits

Programs are statically checked for operand validity, stack underflow, maximum stack depth and instruction limits. Runtime rejects non-finite values, unsafe arithmetic and invalid ranges. There are no unbounded branches or loops in this policy dialect.

MIDI source, compiler/dialect version, normalized IR, source and IR hashes, input vector, output, instruction count, stack analysis, rejection reason and trace hash are retained for simulations and activations. The conventional fallback rules engine remains authoritative when the Velato worker is unavailable or rejects a program.
