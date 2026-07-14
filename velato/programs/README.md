# Velato MIDI policies

`default-watchlist-novelty-v1.mid` is the versioned policy used by the reference vertical slice. Its SHA-256 is `203c4ded7e45fcd2ed614323dacfc6f480d71f1d165e785041461140baf62bea`.

The default policy remains encoded entirely with MIDI channel `0`, so the expanded compiler is backwards-compatible with the original checked-in source. It computes a weighted score from watchlist match, novelty, entity relevance and source diversity; stores severity `2`, routing code `1` and no suppression.

SignalChord Velato 1.1 extends the instruction set through MIDI channels `1`–`3` while retaining interval-based commands:

- Channel `0`: legacy core and output stores.
- Channel `1`: safe numeric operations.
- Channel `2`: comparisons and boolean logic.
- Channel `3`: stack operations, local registers and output reads.

For operand-bearing instructions, velocity is interpreted as follows:

- `PUSH_CONST`: `velocity - 1`, an integer from `0` to `126` in MIDI source.
- `LOAD_INPUT`: `velocity - 1` indexes the fixed input-register list.
- `LOAD_LOCAL` / `STORE_LOCAL`: `velocity - 1` selects local register `0`–`15`.

All other instructions ignore velocity. SysEx and unsupported MIDI channels are rejected. The API can also compile the auditable assembly format shown in `extended-core-example.vasm` into deterministic MIDI.

The worker records MIDI checksum, dialect version, normalized IR hash, static analysis and deterministic trace hash. If parsing or validation fails, execution fails closed to the conventional fallback IR and marks the result accordingly.
