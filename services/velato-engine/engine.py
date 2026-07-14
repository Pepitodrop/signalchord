from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from io import BytesIO
from math import ceil, floor, isfinite, pow as math_pow, sqrt
from typing import Mapping, Sequence
import json
import re

import mido
from pydantic import BaseModel, Field

DIALECT_VERSION = "signalchord-velato-1.1.0"
MAX_LOCALS = 16
DEFAULT_MAX_INSTRUCTIONS = 512
DEFAULT_MAX_STACK = 64

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

OUTPUTS = (
    "alert_score",
    "severity_code",
    "routing_code",
    "suppressed",
)


class Op(str, Enum):
    # Bank 0: backwards-compatible core.
    HALT = "HALT"
    PUSH_CONST = "PUSH_CONST"
    LOAD_INPUT = "LOAD_INPUT"
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    GT = "GT"
    SELECT = "SELECT"
    STORE_SCORE = "STORE_SCORE"
    STORE_SEVERITY = "STORE_SEVERITY"
    STORE_ROUTE = "STORE_ROUTE"
    STORE_SUPPRESS = "STORE_SUPPRESS"

    # Bank 1: safe numeric operations.
    MIN = "MIN"
    MAX = "MAX"
    DIV = "DIV"
    MOD = "MOD"
    NEG = "NEG"
    ABS = "ABS"
    CLAMP = "CLAMP"
    FLOOR = "FLOOR"
    CEIL = "CEIL"
    ROUND = "ROUND"
    POW = "POW"
    SQRT = "SQRT"

    # Bank 2: comparisons and boolean operations.
    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LTE = "LTE"
    GTE = "GTE"
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    NOT = "NOT"
    IS_ZERO = "IS_ZERO"
    BETWEEN = "BETWEEN"
    SIGN = "SIGN"

    # Bank 3: stack, local registers and output introspection.
    DUP = "DUP"
    SWAP = "SWAP"
    OVER = "OVER"
    DROP = "DROP"
    LOAD_LOCAL = "LOAD_LOCAL"
    STORE_LOCAL = "STORE_LOCAL"
    NOP = "NOP"
    STACK_DEPTH = "STACK_DEPTH"
    LOAD_SCORE = "LOAD_SCORE"
    LOAD_SEVERITY = "LOAD_SEVERITY"
    LOAD_ROUTE = "LOAD_ROUTE"
    LOAD_SUPPRESS = "LOAD_SUPPRESS"


@dataclass(frozen=True)
class MidiNote:
    note: int
    velocity: int
    channel: int = 0


@dataclass(frozen=True)
class Instruction:
    op: Op
    arg: float | int | str | None = None


class ProgramAnalysis(BaseModel):
    instruction_count: int = Field(ge=1)
    max_stack_depth: int = Field(ge=0)
    final_stack_depth: int = Field(ge=0)
    required_inputs: list[str]
    local_registers: list[int]
    outputs_written: list[str]
    warnings: list[str]


class PolicyResult(BaseModel):
    alert_score: int = Field(ge=0, le=100)
    severity_code: int = Field(ge=0, le=9)
    routing_code: int = Field(ge=0, le=255)
    suppressed: bool
    instructions_executed: int
    max_stack_depth: int
    trace_hash: str


INSTRUCTION_BANKS: dict[int, dict[int, Op]] = {
    0: {
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
    },
    1: {
        0: Op.MIN,
        1: Op.MAX,
        2: Op.DIV,
        3: Op.MOD,
        4: Op.NEG,
        5: Op.ABS,
        6: Op.CLAMP,
        7: Op.FLOOR,
        8: Op.CEIL,
        9: Op.ROUND,
        10: Op.POW,
        11: Op.SQRT,
    },
    2: {
        0: Op.EQ,
        1: Op.NE,
        2: Op.LT,
        3: Op.LTE,
        4: Op.GTE,
        5: Op.AND,
        6: Op.OR,
        7: Op.XOR,
        8: Op.NOT,
        9: Op.IS_ZERO,
        10: Op.BETWEEN,
        11: Op.SIGN,
    },
    3: {
        0: Op.DUP,
        1: Op.SWAP,
        2: Op.OVER,
        3: Op.DROP,
        4: Op.LOAD_LOCAL,
        5: Op.STORE_LOCAL,
        6: Op.NOP,
        7: Op.STACK_DEPTH,
        8: Op.LOAD_SCORE,
        9: Op.LOAD_SEVERITY,
        10: Op.LOAD_ROUTE,
        11: Op.LOAD_SUPPRESS,
    },
}

OP_ENCODING: dict[Op, tuple[int, int]] = {
    op: (bank, interval)
    for bank, instructions in INSTRUCTION_BANKS.items()
    for interval, op in instructions.items()
}

OPERAND_OPS = {Op.PUSH_CONST, Op.LOAD_INPUT, Op.LOAD_LOCAL, Op.STORE_LOCAL}
LOCAL_OPS = {Op.LOAD_LOCAL, Op.STORE_LOCAL}
OUTPUT_STORE_OPS = {
    Op.STORE_SCORE: "alert_score",
    Op.STORE_SEVERITY: "severity_code",
    Op.STORE_ROUTE: "routing_code",
    Op.STORE_SUPPRESS: "suppressed",
}

STACK_EFFECTS: dict[Op, tuple[int, int]] = {
    Op.HALT: (0, 0),
    Op.PUSH_CONST: (0, 1),
    Op.LOAD_INPUT: (0, 1),
    Op.ADD: (2, 1),
    Op.SUB: (2, 1),
    Op.MUL: (2, 1),
    Op.GT: (2, 1),
    Op.SELECT: (3, 1),
    Op.STORE_SCORE: (1, 0),
    Op.STORE_SEVERITY: (1, 0),
    Op.STORE_ROUTE: (1, 0),
    Op.STORE_SUPPRESS: (1, 0),
    Op.MIN: (2, 1),
    Op.MAX: (2, 1),
    Op.DIV: (2, 1),
    Op.MOD: (2, 1),
    Op.NEG: (1, 1),
    Op.ABS: (1, 1),
    Op.CLAMP: (3, 1),
    Op.FLOOR: (1, 1),
    Op.CEIL: (1, 1),
    Op.ROUND: (1, 1),
    Op.POW: (2, 1),
    Op.SQRT: (1, 1),
    Op.EQ: (2, 1),
    Op.NE: (2, 1),
    Op.LT: (2, 1),
    Op.LTE: (2, 1),
    Op.GTE: (2, 1),
    Op.AND: (2, 1),
    Op.OR: (2, 1),
    Op.XOR: (2, 1),
    Op.NOT: (1, 1),
    Op.IS_ZERO: (1, 1),
    Op.BETWEEN: (3, 1),
    Op.SIGN: (1, 1),
    Op.DUP: (1, 2),
    Op.SWAP: (2, 2),
    Op.OVER: (2, 3),
    Op.DROP: (1, 0),
    Op.LOAD_LOCAL: (0, 1),
    Op.STORE_LOCAL: (1, 0),
    Op.NOP: (0, 0),
    Op.STACK_DEPTH: (0, 1),
    Op.LOAD_SCORE: (0, 1),
    Op.LOAD_SEVERITY: (0, 1),
    Op.LOAD_ROUTE: (0, 1),
    Op.LOAD_SUPPRESS: (0, 1),
}


def parse_midi(data: bytes, max_bytes: int = 128_000, max_notes: int = 1024) -> list[MidiNote]:
    if len(data) > max_bytes:
        raise ValueError("MIDI exceeds byte limit")
    midi = mido.MidiFile(file=BytesIO(data))
    notes: list[MidiNote] = []
    for track in midi.tracks:
        for msg in track:
            if msg.type == "sysex":
                raise ValueError("SysEx is unsupported")
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(
                    MidiNote(
                        note=int(msg.note),
                        velocity=int(msg.velocity),
                        channel=int(msg.channel),
                    )
                )
            if len(notes) > max_notes:
                raise ValueError("MIDI exceeds note limit")
    if len(notes) < 2:
        raise ValueError("program requires root and instruction notes")
    return notes


def _decode_operand(op: Op, velocity: int) -> float | int | str | None:
    operand = velocity - 1
    if op is Op.PUSH_CONST:
        return operand
    if op is Op.LOAD_INPUT:
        if operand < 0 or operand >= len(INPUTS):
            raise ValueError("invalid input register operand")
        return INPUTS[operand]
    if op in LOCAL_OPS:
        if operand < 0 or operand >= MAX_LOCALS:
            raise ValueError("invalid local register operand")
        return operand
    return None


def compile_notes(notes: Sequence[MidiNote]) -> list[Instruction]:
    root = notes[0].note
    ir: list[Instruction] = []
    for event in notes[1:]:
        interval = (event.note - root) % 12
        bank = INSTRUCTION_BANKS.get(event.channel)
        if bank is None:
            raise ValueError(f"unsupported instruction bank {event.channel}")
        op = bank[interval]
        ir.append(Instruction(op, _decode_operand(op, event.velocity)))
        if op is Op.HALT:
            break
    if not ir or ir[-1].op is not Op.HALT:
        ir.append(Instruction(Op.HALT))
    analyze_ir(ir)
    return ir


def _validate_instruction(instruction: Instruction) -> None:
    if instruction.op is Op.PUSH_CONST:
        if not isinstance(instruction.arg, (int, float)) or not isfinite(float(instruction.arg)):
            raise ValueError("PUSH_CONST requires a finite numeric operand")
    elif instruction.op is Op.LOAD_INPUT:
        if not isinstance(instruction.arg, str) or instruction.arg not in INPUTS:
            raise ValueError("LOAD_INPUT requires a valid input register")
    elif instruction.op in LOCAL_OPS:
        if not isinstance(instruction.arg, int) or not 0 <= instruction.arg < MAX_LOCALS:
            raise ValueError(f"{instruction.op.value} requires a local register from 0 to {MAX_LOCALS - 1}")
    elif instruction.arg is not None:
        raise ValueError(f"{instruction.op.value} does not accept an operand")


def analyze_ir(
    ir: Sequence[Instruction],
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    max_stack: int = DEFAULT_MAX_STACK,
) -> ProgramAnalysis:
    if not ir:
        raise ValueError("program is empty")
    if len(ir) > max_instructions:
        raise ValueError("instruction limit exceeded")

    depth = 0
    max_depth = 0
    required_inputs: set[str] = set()
    local_registers: set[int] = set()
    outputs_written: set[str] = set()
    warnings: list[str] = []
    halted = False
    executed_count = 0

    for index, instruction in enumerate(ir):
        if halted:
            warnings.append(f"instruction {index} is unreachable after HALT")
            continue
        _validate_instruction(instruction)
        executed_count += 1
        pops, pushes = STACK_EFFECTS[instruction.op]
        if depth < pops:
            raise ValueError(f"static stack underflow at instruction {index} ({instruction.op.value})")
        depth = depth - pops + pushes
        max_depth = max(max_depth, depth)
        if max_depth > max_stack:
            raise ValueError("stack limit exceeded")
        if instruction.op is Op.LOAD_INPUT:
            assert isinstance(instruction.arg, str)
            required_inputs.add(instruction.arg)
        elif instruction.op in LOCAL_OPS:
            assert isinstance(instruction.arg, int)
            local_registers.add(instruction.arg)
        if instruction.op in OUTPUT_STORE_OPS:
            outputs_written.add(OUTPUT_STORE_OPS[instruction.op])
        if instruction.op is Op.HALT:
            halted = True

    if not halted:
        warnings.append("program has no explicit HALT")
    missing_outputs = [name for name in OUTPUTS if name not in outputs_written]
    if missing_outputs:
        warnings.append("outputs not written: " + ", ".join(missing_outputs))

    return ProgramAnalysis(
        instruction_count=executed_count,
        max_stack_depth=max_depth,
        final_stack_depth=depth,
        required_inputs=sorted(required_inputs),
        local_registers=sorted(local_registers),
        outputs_written=[name for name in OUTPUTS if name in outputs_written],
        warnings=warnings,
    )


def execute(
    ir: Sequence[Instruction],
    inputs: Mapping[str, float],
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    max_stack: int = DEFAULT_MAX_STACK,
) -> PolicyResult:
    analysis = analyze_ir(ir, max_instructions=max_instructions, max_stack=max_stack)
    normalized_inputs: dict[str, float] = {}
    for key in INPUTS:
        if key not in inputs:
            raise ValueError(f"missing input {key}")
        value = float(inputs[key])
        if not isfinite(value):
            raise ValueError(f"input {key} must be finite")
        normalized_inputs[key] = value

    stack: list[float] = []
    locals_: list[float] = [0.0] * MAX_LOCALS
    score = severity = route = 0
    suppressed = False
    trace: list[dict[str, object]] = []
    max_depth = 0

    def pop() -> float:
        if not stack:
            raise ValueError("stack underflow")
        return stack.pop()

    def push(value: float | int | bool) -> None:
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError("operation produced a non-finite value")
        stack.append(numeric)

    def pop_binary() -> tuple[float, float]:
        b = pop()
        a = pop()
        return a, b

    for count, instruction in enumerate(ir, 1):
        if count > max_instructions:
            raise ValueError("instruction limit exceeded")
        depth_before = len(stack)
        if instruction.op is Op.HALT:
            trace.append(
                {
                    "op": instruction.op.value,
                    "arg": instruction.arg,
                    "depth_before": depth_before,
                    "depth_after": depth_before,
                }
            )
            break

        op = instruction.op
        if op is Op.PUSH_CONST:
            assert isinstance(instruction.arg, (int, float))
            push(instruction.arg)
        elif op is Op.LOAD_INPUT:
            assert isinstance(instruction.arg, str)
            push(normalized_inputs[instruction.arg])
        elif op in {Op.ADD, Op.SUB, Op.MUL, Op.MIN, Op.MAX, Op.GT, Op.EQ, Op.NE, Op.LT, Op.LTE, Op.GTE, Op.AND, Op.OR, Op.XOR}:
            a, b = pop_binary()
            values = {
                Op.ADD: a + b,
                Op.SUB: a - b,
                Op.MUL: a * b,
                Op.MIN: min(a, b),
                Op.MAX: max(a, b),
                Op.GT: a > b,
                Op.EQ: a == b,
                Op.NE: a != b,
                Op.LT: a < b,
                Op.LTE: a <= b,
                Op.GTE: a >= b,
                Op.AND: bool(a) and bool(b),
                Op.OR: bool(a) or bool(b),
                Op.XOR: bool(a) ^ bool(b),
            }
            push(values[op])
        elif op is Op.DIV:
            a, b = pop_binary()
            if b == 0:
                raise ValueError("division by zero")
            push(a / b)
        elif op is Op.MOD:
            a, b = pop_binary()
            if b == 0:
                raise ValueError("modulo by zero")
            push(a % b)
        elif op is Op.POW:
            a, b = pop_binary()
            try:
                push(math_pow(a, b))
            except (OverflowError, ValueError) as error:
                raise ValueError("invalid exponentiation") from error
        elif op in {Op.NEG, Op.ABS, Op.FLOOR, Op.CEIL, Op.ROUND, Op.SQRT, Op.NOT, Op.IS_ZERO, Op.SIGN}:
            value = pop()
            if op is Op.NEG:
                push(-value)
            elif op is Op.ABS:
                push(abs(value))
            elif op is Op.FLOOR:
                push(floor(value))
            elif op is Op.CEIL:
                push(ceil(value))
            elif op is Op.ROUND:
                push(round(value))
            elif op is Op.SQRT:
                if value < 0:
                    raise ValueError("square root of negative value")
                push(sqrt(value))
            elif op is Op.NOT:
                push(not bool(value))
            elif op is Op.IS_ZERO:
                push(value == 0)
            else:
                push(-1 if value < 0 else 1 if value > 0 else 0)
        elif op is Op.CLAMP:
            upper, lower, value = pop(), pop(), pop()
            if lower > upper:
                raise ValueError("CLAMP lower bound exceeds upper bound")
            push(max(lower, min(upper, value)))
        elif op is Op.BETWEEN:
            upper, lower, value = pop(), pop(), pop()
            if lower > upper:
                raise ValueError("BETWEEN lower bound exceeds upper bound")
            push(lower <= value <= upper)
        elif op is Op.SELECT:
            false_value, true_value, condition = pop(), pop(), pop()
            push(true_value if condition else false_value)
        elif op is Op.DUP:
            value = pop()
            push(value)
            push(value)
        elif op is Op.SWAP:
            a, b = pop_binary()
            push(b)
            push(a)
        elif op is Op.OVER:
            a, b = pop_binary()
            push(a)
            push(b)
            push(a)
        elif op is Op.DROP:
            pop()
        elif op is Op.LOAD_LOCAL:
            assert isinstance(instruction.arg, int)
            push(locals_[instruction.arg])
        elif op is Op.STORE_LOCAL:
            assert isinstance(instruction.arg, int)
            locals_[instruction.arg] = pop()
        elif op is Op.NOP:
            pass
        elif op is Op.STACK_DEPTH:
            push(len(stack))
        elif op is Op.LOAD_SCORE:
            push(score)
        elif op is Op.LOAD_SEVERITY:
            push(severity)
        elif op is Op.LOAD_ROUTE:
            push(route)
        elif op is Op.LOAD_SUPPRESS:
            push(suppressed)
        elif op is Op.STORE_SCORE:
            score = max(0, min(100, round(pop())))
        elif op is Op.STORE_SEVERITY:
            severity = max(0, min(9, round(pop())))
        elif op is Op.STORE_ROUTE:
            route = max(0, min(255, round(pop())))
        elif op is Op.STORE_SUPPRESS:
            suppressed = bool(pop())
        else:
            raise ValueError(f"unsupported operation {op.value}")

        if len(stack) > max_stack:
            raise ValueError("stack limit exceeded")
        max_depth = max(max_depth, len(stack))
        trace.append(
            {
                "op": instruction.op.value,
                "arg": instruction.arg,
                "depth_before": depth_before,
                "depth_after": len(stack),
                "top": stack[-1] if stack else None,
            }
        )

    digest = sha256(json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PolicyResult(
        alert_score=score,
        severity_code=severity,
        routing_code=route,
        suppressed=suppressed,
        instructions_executed=len(trace),
        max_stack_depth=max(max_depth, analysis.max_stack_depth),
        trace_hash=digest,
    )


def default_policy_ir() -> list[Instruction]:
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


def serialize_ir(ir: Sequence[Instruction]) -> list[dict[str, object]]:
    return [{"op": instruction.op.value, "arg": instruction.arg} for instruction in ir]


def deserialize_ir(items: Sequence[Mapping[str, object]]) -> list[Instruction]:
    ir: list[Instruction] = []
    for index, item in enumerate(items):
        try:
            op = Op(str(item["op"]))
        except (KeyError, ValueError) as error:
            raise ValueError(f"invalid operation at instruction {index}") from error
        ir.append(Instruction(op, item.get("arg")))
    analyze_ir(ir)
    return ir


def ir_sha256(ir: Sequence[Instruction]) -> str:
    return sha256(json.dumps(serialize_ir(ir), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def decompile(ir: Sequence[Instruction]) -> str:
    lines: list[str] = []
    for index, instruction in enumerate(ir):
        operand = "" if instruction.arg is None else f" {instruction.arg}"
        bank, interval = OP_ENCODING[instruction.op]
        lines.append(f"{index:03d}: {instruction.op.value}{operand}  # channel={bank} interval={interval}")
    return "\n".join(lines)


_ASSEMBLY_LINE = re.compile(r"^(?:(?P<index>\d+):\s*)?(?P<op>[A-Z_]+)(?:\s+(?P<arg>[^#]+?))?\s*(?:#.*)?$")


def parse_assembly(source: str, max_lines: int = 1024) -> list[Instruction]:
    if len(source.encode()) > 128_000:
        raise ValueError("assembly exceeds byte limit")
    ir: list[Instruction] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if len(ir) >= max_lines:
            raise ValueError("assembly exceeds instruction limit")
        match = _ASSEMBLY_LINE.fullmatch(line)
        if not match:
            raise ValueError(f"invalid assembly syntax on line {line_number}")
        try:
            op = Op(match.group("op"))
        except ValueError as error:
            raise ValueError(f"unknown operation on line {line_number}") from error
        raw_arg = match.group("arg")
        arg: float | int | str | None = None
        if op is Op.LOAD_INPUT:
            arg = raw_arg.strip() if raw_arg else None
        elif op in LOCAL_OPS:
            try:
                arg = int(raw_arg.strip()) if raw_arg else None
            except ValueError as error:
                raise ValueError(f"invalid local register on line {line_number}") from error
        elif op is Op.PUSH_CONST:
            try:
                value = float(raw_arg.strip()) if raw_arg else None
            except ValueError as error:
                raise ValueError(f"invalid constant on line {line_number}") from error
            if value is not None and value.is_integer():
                arg = int(value)
            else:
                arg = value
        elif raw_arg:
            raise ValueError(f"{op.value} does not accept an operand on line {line_number}")
        ir.append(Instruction(op, arg))
    if not ir or ir[-1].op is not Op.HALT:
        ir.append(Instruction(Op.HALT))
    analyze_ir(ir)
    return ir


def _encode_velocity(instruction: Instruction) -> int:
    if instruction.op is Op.PUSH_CONST:
        if not isinstance(instruction.arg, (int, float)):
            raise ValueError("PUSH_CONST requires a numeric operand")
        value = float(instruction.arg)
        if not value.is_integer() or not 0 <= value <= 126:
            raise ValueError("MIDI encoding supports integer constants from 0 to 126")
        return int(value) + 1
    if instruction.op is Op.LOAD_INPUT:
        if not isinstance(instruction.arg, str) or instruction.arg not in INPUTS:
            raise ValueError("invalid input register")
        return INPUTS.index(instruction.arg) + 1
    if instruction.op in LOCAL_OPS:
        if not isinstance(instruction.arg, int) or not 0 <= instruction.arg < MAX_LOCALS:
            raise ValueError("invalid local register")
        return instruction.arg + 1
    return 64


def encode_midi(
    ir: Sequence[Instruction],
    root_note: int = 60,
    ticks_per_beat: int = 480,
    note_ticks: int = 120,
) -> bytes:
    analyze_ir(ir)
    if not 0 <= root_note <= 116:
        raise ValueError("root note must be between 0 and 116")
    if ticks_per_beat <= 0 or note_ticks <= 0:
        raise ValueError("MIDI timing values must be positive")

    midi = mido.MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.Message("note_on", note=root_note, velocity=64, channel=0, time=0))
    track.append(mido.Message("note_off", note=root_note, velocity=0, channel=0, time=note_ticks))
    for instruction in ir:
        bank, interval = OP_ENCODING[instruction.op]
        note = root_note + interval
        velocity = _encode_velocity(instruction)
        track.append(mido.Message("note_on", note=note, velocity=velocity, channel=bank, time=0))
        track.append(mido.Message("note_off", note=note, velocity=0, channel=bank, time=note_ticks))
    output = BytesIO()
    midi.save(file=output)
    return output.getvalue()


def capabilities() -> dict[str, object]:
    return {
        "dialect_version": DIALECT_VERSION,
        "inputs": list(INPUTS),
        "outputs": list(OUTPUTS),
        "limits": {
            "max_instructions": DEFAULT_MAX_INSTRUCTIONS,
            "max_stack": DEFAULT_MAX_STACK,
            "local_registers": MAX_LOCALS,
            "midi_banks": sorted(INSTRUCTION_BANKS),
        },
        "instruction_banks": {
            str(bank): {str(interval): op.value for interval, op in instructions.items()}
            for bank, instructions in INSTRUCTION_BANKS.items()
        },
    }
