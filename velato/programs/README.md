# Velato MIDI policies

SignalChord uses a constrained dialect inspired by [Velato](https://velato.net/), the esoteric programming language in which executable source is represented as MIDI music. SignalChord keeps the musical instruction model while compiling programs into a sealed, deterministic policy VM.

`default-watchlist-novelty-v1.mid` is the versioned policy used by the reference vertical slice. Its SHA-256 is `203c4ded7e45fcd2ed614323dacfc6f480d71f1d165e785041461140baf62bea`.

The default policy remains encoded entirely with MIDI channel `0`, so the expanded compiler is backwards-compatible with the original checked-in source. It computes a weighted score from watchlist match, novelty, entity relevance and source diversity; stores severity `2`, routing code `1` and no suppression.

## Main features

1. **Music is executable policy source.** Pitch intervals select instructions, MIDI channels select instruction banks and note velocity carries bounded operands.
2. **Deterministic and auditable execution.** MIDI and `.vasm` assembly compile to the same sealed IR with static stack analysis, source/IR hashes, bounded execution and reproducible traces.
3. **Operationally useful outputs.** Every production policy can calculate an alert score, assign severity, choose a routing queue and suppress unsafe or low-value material.
4. **Safe by construction.** The dialect has no filesystem, shell, network, unbounded loop or arbitrary-code instructions.

## Functional song programs

These pieces are both musical instruction sequences and real SignalChord policies. They are not decorative assets: every program writes all four required outputs and is round-trip tested through assembly, MIDI encoding, MIDI decoding and execution.

| Program | Broad musical character | Operational role | Primary route |
| --- | --- | --- | --- |
| [`watchlist-privateer.vasm`](watchlist-privateer.vasm) | Original cinematic seafaring action pulse | Escalates corroborated, recent watchlist stories; discounts contradictions and suppresses low-trust material. | `7` urgent watchlist |
| [`city-waltz.vasm`](city-waltz.vasm) | Original modern German indie-pop waltz pulse | Scores local relevance, entity importance, source diversity, trust and recency. | `4` local impact |
| [`contradiction-canon.vasm`](contradiction-canon.vasm) | Original interlocking canon-like comparison figures | Detects contradiction-heavy stories that deserve investigation and suppresses unsupported noise. | `5` contradiction review |
| [`source-trust-nocturne.vasm`](source-trust-nocturne.vasm) | Original restrained nocturne contour | Acts as a source-quality gate using trust, corroboration, diversity and recency. | `2` trusted-source review |
| [`novelty-rondo.vasm`](novelty-rondo.vasm) | Original returning novelty-recency motif | Detects emerging stories with relevant entities and graph position. | `3` discovery |
| [`live-graph-minute.vasm`](live-graph-minute.vasm) | Original one-minute graph pulse at 100 BPM | Calculates graph momentum from centrality, novelty, recency and diversity; routes mature graph signals and suppresses low-trust or contradiction-heavy material. | `6` graph momentum |

The first two pieces use only broad genre and rhythmic characteristics requested for the showcase. They do not reproduce the melody, harmony or arrangement of an existing copyrighted song. `Live Graph Minute` contains exactly 100 executable instructions; the Live Lab plays one instruction per beat at 100 BPM for an approximately one-minute performance.

## Policy Studio playback easter egg

Open **Policy Studio** in the web application and select **♪ Reveal scores**. Every program card provides:

- the complete executable note sequence, including its MIDI instruction-bank number;
- a **Play code** control that sonifies the real opcode order through browser Web Audio;
- a **Download `.mid`** control that generates an executable Standard MIDI file with the actual channels, intervals, velocities and operands;
- a plain-language explanation directly under the player describing the score, severity, routing and suppression behavior;
- the checked-in `.vasm` source in an expandable panel.

The browser playback is an audible interpretation of the same instructions. The downloaded MIDI remains machine-executable by the constrained Velato engine rather than being a separate decorative audio asset.

The separate authenticated **Live Lab** at `/lab.html` exposes `Live Graph Minute`, its source and its complete approximately one-minute Web Audio performance alongside tenant-scoped graph-growth and pipeline visualizations.

## Instruction banks

SignalChord Velato 1.1 extends the instruction set through MIDI channels `1`–`3` while retaining interval-based commands:

- Channel `0`: legacy core and output stores.
- Channel `1`: safe numeric operations.
- Channel `2`: comparisons and boolean logic.
- Channel `3`: stack operations, local registers and output reads.

For operand-bearing instructions, velocity is interpreted as follows:

- `PUSH_CONST`: `velocity - 1`, an integer from `0` to `126` in MIDI source.
- `LOAD_INPUT`: `velocity - 1` indexes the fixed input-register list.
- `LOAD_LOCAL` / `STORE_LOCAL`: `velocity - 1` selects local register `0`–`15`.

All other instructions ignore velocity. SysEx and unsupported MIDI channels are rejected. The API compiles any checked-in `.vasm` source into deterministic MIDI through `POST /v1/assemble`, and `POST /v1/simulate` executes either the assembly or resulting MIDI.

The worker records MIDI checksum, dialect version, normalized IR hash, static analysis and deterministic trace hash. If parsing or validation fails, execution fails closed to the conventional fallback IR and marks the result accordingly.
