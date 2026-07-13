# Default Velato MIDI policies

`default-watchlist-novelty-v1.mid` is the versioned policy used by the first vertical slice. Its SHA-256 is `203c4ded7e45fcd2ed614323dacfc6f480d71f1d165e785041461140baf62bea`.

SignalChord's documented minimal Velato subset retains the public language's root-note/interval instruction model. The first positive-velocity note defines the root. Every subsequent positive-velocity note selects an instruction by its pitch interval modulo 12. For the two operand-bearing instructions, MIDI velocity encodes a constrained operand:

- `PUSH_CONST`: `velocity - 1`, producing an integer from 0 to 126.
- `LOAD_INPUT`: `velocity - 1` indexes the fixed input-register list.

All other instructions ignore velocity. Notes are sequenced so the policy can be heard as a short composition. SysEx and unsupported intervals are rejected. This subset is intentionally not a general-purpose Velato runtime.

The policy computes a weighted score from watchlist match, novelty, entity relevance and source diversity; it stores severity 2, routing code 1 and no suppression. The worker records the MIDI checksum, normalized IR and deterministic trace hash. If parsing or validation fails, execution fails closed to the conventional fallback IR and marks the result accordingly.
