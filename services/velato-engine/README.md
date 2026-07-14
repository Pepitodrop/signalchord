# SignalChord Policy Composer / Velato engine

SignalChord uses a deliberately constrained Velato-inspired policy dialect. Programs remain Standard MIDI files whose pitch intervals encode instructions, but they compile into a sealed, deterministic stack-machine IR rather than executing arbitrary interpreter behavior.

The implementation preserves the original checked-in channel-0 policy byte-for-byte while extending the language through MIDI instruction banks:

| MIDI channel | Bank | Purpose |
| --- | --- | --- |
| `0` | Core | Constants, fixed inputs, arithmetic, selection and output stores. |
| `1` | Numeric | Min/max, safe division/modulo, unary math, clamp, rounding, power and square root. |
| `2` | Logic | Comparisons, boolean operators, inclusive range checks and sign. |
| `3` | State | Stack manipulation, 16 bounded local registers, no-op, stack depth and output reads. |

The first positive-velocity note defines the root pitch. Every later positive-velocity note selects an instruction by `(note - root) mod 12`; its MIDI channel selects the instruction bank. Velocity carries operands only for `PUSH_CONST`, `LOAD_INPUT`, `LOAD_LOCAL` and `STORE_LOCAL`.

## Authoring and API

The engine supports both MIDI and a small auditable assembly notation:

```text
LOAD_INPUT novelty
PUSH_CONST 100
MUL
PUSH_CONST 0
PUSH_CONST 100
CLAMP
STORE_SCORE
HALT
```

- `GET /v1/capabilities` returns the dialect version, registers, limits and complete bank map.
- `POST /v1/validate` compiles MIDI and returns normalized IR, static stack analysis and hashes.
- `POST /v1/assemble` validates assembly and renders a deterministic MIDI program.
- `POST /v1/simulate` evaluates MIDI, assembly or the checked-in default policy.

## Safety properties

Before execution the engine performs static operand and stack analysis. Runtime checks reject stack underflow, division or modulo by zero, invalid powers, square roots of negative values, non-finite inputs/results, invalid local registers, unsupported MIDI banks, SysEx, oversized MIDI and instruction/stack-limit violations.

The IR has no filesystem, shell or network instructions and no unbounded jumps or loops. Execution is deterministic and bounded by instruction, stack, MIDI-byte and note limits. Production deployment must additionally enforce OS/container CPU, memory, wall-clock, read-only filesystem, seccomp and egress limits as described in the threat model and Helm configuration.

The default worker loads `velato/programs/default-watchlist-novelty-v1.mid`, records the source and IR hashes, dialect version and static analysis, and falls back to the conventional policy IR only when the MIDI policy cannot be loaded or validated.
