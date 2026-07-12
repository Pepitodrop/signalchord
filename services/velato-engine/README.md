# SignalChord Policy Composer / Velato engine

Velato programs are Standard MIDI files whose note intervals encode instructions. SignalChord parses MIDI, compiles a documented supported subset to a sealed IR, validates it, and runs a deterministic interpreter with fixed input/output registers and strict instruction/stack limits. Unsupported instructions and SysEx are rejected; fallback rules remain available.

The first vertical slice loads `velato/programs/default-watchlist-novelty-v1.mid`, verifies its checksum, compiles it and executes the resulting IR. A checked-in conventional fallback IR is tested for output parity and is used only if the MIDI source cannot be loaded or validated.

This initial process-level sandbox already forbids filesystem, shell and network operations in the IR itself. Production deployment must additionally enforce OS/container CPU, memory, wall-clock, read-only filesystem, seccomp and egress limits as described in the threat model and Helm configuration.
