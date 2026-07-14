# ADR 0005 — Velato compiles to a constrained policy IR

**Status:** Accepted; extended dialect versioned as `signalchord-velato-1.1.0`

## Decision

Velato-inspired MIDI is parsed as untrusted input and compiled into a sealed, versioned stack-machine IR with whitelisted scalar operations and fixed registers. The first note defines a root pitch; subsequent pitch intervals select instructions. MIDI channel `0` preserves the original core mapping, while channels `1`–`3` provide versioned numeric, logic and bounded local-state banks.

Execution is deterministic and isolated with byte, note, instruction, stack, CPU, wall-time and memory limits. Static analysis rejects invalid operands and stack underflow before execution. Runtime rejects unsafe arithmetic and non-finite values. The IR deliberately has no filesystem, shell, network or unbounded control-flow instructions. A conventional fallback rules engine remains available.

## Consequences

SignalChord does not execute arbitrary historical Velato-interpreter behavior and does not claim full canonical compatibility. Unsupported banks or instructions are rejected with human-readable decompilation and validation errors. MIDI source, dialect/compiler version, IR, source and IR hashes, inputs, outputs, static analysis and trace hash are audited.

The channel-bank extension preserves existing channel-0 policies while allowing richer policy composition without weakening determinism or sandboxability. The capability endpoint is the source of truth for the exact deployed instruction map.
