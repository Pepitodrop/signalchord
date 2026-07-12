# SignalChord Policy Composer / Velato engine

Velato programs are MIDI files whose note intervals encode instructions. SignalChord parses MIDI, compiles a supported subset to a sealed IR, validates it, and runs a deterministic interpreter with fixed input/output registers and strict instruction/stack limits. Unsupported instructions and SysEx are rejected; fallback rules remain available.
