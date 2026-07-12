from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from io import BytesIO
from typing import Mapping
import json

import mido
from pydantic import BaseModel, Field

INPUTS = (
    "source_trust",
    "corroboration_count",
    "contradiction_count",
    "novelty",
    "entity_relevance",
    "graph_centrality",
    "geographic_relevance",
    "watchlist_match",
    "recency",
    "source_diversity",
)


class Op(str, Enum):
    PUSH_CONST = "PUSH_CONST"
    LOAD_INPUT = "LOAD_INPUT"
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    MIN = "MIN"
    MAX = "MAX"
    GT = "GT"
    SELECT = "SELECT"
    STORE_SCORE = "STORE_SCORE"
    STORE_SEVERITY = "STORE_SEVERITY"
    STORE_ROUTE = "STORE_ROUTE"
    STORE_SUPPRESS = "STORE_SUPPRESS"
    HALT = "HALT"


@dataclass(frozen=True)
class MidiNote:
    note: int
    velocity: int


@dataclass(frozen=True)
class Instruction:
    op: Op
    arg: float | int | str | None = None


class PolicyResult(BaseModel):
    alert_score: int = Field(ge=0, le=100)
    severity_code: int = Field(ge=0, le=9)
    routing_code: int = Field(ge=0, le=255)
    suppressed: bool
    instructions_executed: int
    trace_hash: str


INTERVAL_OP = {
    0: Op.HALT,
    1: Op.PUSH_CONST,
    2: Op.LOAD_INPUT,
    3: Op.ADD,
    4: Op.SUB,
    5: Op.MUL,
    6: Op.GT,
    7: Op.SELECT,
    8: Op.STORE_SCORE,
    9: Op.STORE_SEVERITY,
    10: Op.STORE_ROUTE,
    11: Op.STORE_SUPPRESS,
}


def parse_midi(
    data: bytes, max_bytes: int = 128_000, max_notes: int = 1024
) -> list[MidiNote]:
    if len(data) > max_bytes:
        raise ValueError("MIDI exceeds byte limit")
    midi = mido.MidiFile(file=BytesIO(data))
    notes: list[MidiNote] = []
    for track in midi.tracks:
        for msg in track:
            if msg.type == "sysex":
                raise ValueError("SysEx is unsupported")
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(MidiNote(note=int(msg.note), velocity=int(msg.velocity)))
            if len(notes) > max_notes:
                raise ValueError("MIDI exceeds note limit")
    if len(notes) < 2:
        raise ValueError("program requires root and instruction notes")
    return notes


def compile_notes(notes: list[MidiNote]) -> list[Instruction]:
    root = notes[0].note
    ir: list[Instruction] = []
    for event in notes[1:]:
        interval = (event.note - root) % 12
        op = INTERVAL_OP.get(interval)
        if op is None:
            raise ValueError(f"unsupported interval {interval}")
        arg: float | int | str | None = None
        if op is Op.PUSH_CONST:
            arg = event.velocity - 1
        elif op is Op.LOAD_INPUT:
            register_index = event.velocity - 1
            if register_index < 0 or register_index >= len(INPUTS):
                raise ValueError("invalid input register operand")
            arg = INPUTS[register_index]
        ir.append(Instruction(op, arg))
        if op is Op.HALT:
            break
    if not ir or ir[-1].op is not Op.HALT:
        ir.append(Instruction(Op.HALT))
    return ir


def execute(
    ir: list[Instruction],
    inputs: Mapping[str, float],
    max_instructions: int = 512,
    max_stack: int = 64,
) -> PolicyResult:
    for key in INPUTS:
        if key not in inputs:
            raise ValueError(f"missing input {key}")
    stack: list[float] = []
    score = severity = route = 0
    suppressed = False
    trace: list[dict[str, object]] = []

    def pop() -> float:
        if not stack:
            raise ValueError("stack underflow")
        return stack.pop()

    for count, ins in enumerate(ir, 1):
        if count > max_instructions:
            raise ValueError("instruction limit exceeded")
        trace.append({"op": ins.op.value, "arg": ins.arg, "depth": len(stack)})
        if ins.op is Op.HALT:
            break
        if ins.op is Op.PUSH_CONST:
            stack.append(float(ins.arg or 0))
        elif ins.op is Op.LOAD_INPUT:
            if not isinstance(ins.arg, str) or ins.arg not in INPUTS:
                raise ValueError("invalid input register")
            stack.append(float(inputs[ins.arg]))
        elif ins.op in (Op.ADD, Op.SUB, Op.MUL, Op.MIN, Op.MAX, Op.GT):
            b, a = pop(), pop()
            operations = {
                Op.ADD: a + b,
                Op.SUB: a - b,
                Op.MUL: a * b,
                Op.MIN: min(a, b),
                Op.MAX: max(a, b),
                Op.GT: 1.0 if a > b else 0.0,
            }
            stack.append(operations[ins.op])
        elif ins.op is Op.SELECT:
            false_value, true_value, condition = pop(), pop(), pop()
            stack.append(true_value if condition else false_value)
        elif ins.op is Op.STORE_SCORE:
            score = max(0, min(100, round(pop())))
        elif ins.op is Op.STORE_SEVERITY:
            severity = max(0, min(9, round(pop())))
        elif ins.op is Op.STORE_ROUTE:
            route = max(0, min(255, round(pop())))
        elif ins.op is Op.STORE_SUPPRESS:
            suppressed = bool(pop())
        if len(stack) > max_stack:
            raise ValueError("stack limit exceeded")
    digest = sha256(
        json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return PolicyResult(
        alert_score=score,
        severity_code=severity,
        routing_code=route,
        suppressed=suppressed,
        instructions_executed=len(trace),
        trace_hash=digest,
    )


def default_policy_ir() -> list[Instruction]:
    """Conventional fallback equivalent to the checked-in default MIDI policy."""
    return [
        Instruction(Op.LOAD_INPUT, "watchlist_match"),
        Instruction(Op.PUSH_CONST, 40),
        Instruction(Op.MUL),
        Instruction(Op.LOAD_INPUT, "novelty"),
        Instruction(Op.PUSH_CONST, 25),
        Instruction(Op.MUL),
        Instruction(Op.ADD),
        Instruction(Op.LOAD_INPUT, "entity_relevance"),
        Instruction(Op.PUSH_CONST, 20),
        Instruction(Op.MUL),
        Instruction(Op.ADD),
        Instruction(Op.LOAD_INPUT, "source_diversity"),
        Instruction(Op.PUSH_CONST, 15),
        Instruction(Op.MUL),
        Instruction(Op.ADD),
        Instruction(Op.STORE_SCORE),
        Instruction(Op.PUSH_CONST, 2),
        Instruction(Op.STORE_SEVERITY),
        Instruction(Op.PUSH_CONST, 1),
        Instruction(Op.STORE_ROUTE),
        Instruction(Op.PUSH_CONST, 0),
        Instruction(Op.STORE_SUPPRESS),
        Instruction(Op.HALT),
    ]
