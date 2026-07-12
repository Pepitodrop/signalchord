# ADR 0005 — Velato compiles to a constrained policy IR

**Status:** Accepted with subset review required

## Decision
Velato-compatible MIDI is parsed as untrusted input and compiled into a sealed, versioned stack-machine IR with whitelisted scalar operations and fixed registers. Execution is deterministic and isolated with byte, note, instruction, stack, CPU, wall-time and memory limits. A conventional fallback rules engine remains available.

## Consequences
SignalChord does not execute arbitrary original-interpreter behavior. Unsupported instructions are rejected with a human-readable decompilation error. MIDI source, IR, inputs, outputs and trace hash are audited.
