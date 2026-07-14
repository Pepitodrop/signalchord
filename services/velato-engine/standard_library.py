from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from engine import Instruction, Op, analyze_ir


@dataclass
class PolicyBuilder:
    """Composable, validated macros for the SignalChord Velato policy dialect.

    The builder emits the same sealed IR used by MIDI and assembly programs. It
    never evaluates arbitrary Python, performs I/O, or bypasses VM limits.
    """

    instructions: list[Instruction] = field(default_factory=list)

    def emit(self, op: Op, arg: float | int | str | None = None) -> "PolicyBuilder":
        self.instructions.append(Instruction(op, arg))
        return self

    def extend(self, instructions: Iterable[Instruction]) -> "PolicyBuilder":
        self.instructions.extend(instructions)
        return self

    def constant(self, value: float | int) -> "PolicyBuilder":
        return self.emit(Op.PUSH_CONST, value)

    def input(self, name: str) -> "PolicyBuilder":
        return self.emit(Op.LOAD_INPUT, name)

    def load_local(self, register: int) -> "PolicyBuilder":
        return self.emit(Op.LOAD_LOCAL, register)

    def store_local(self, register: int) -> "PolicyBuilder":
        return self.emit(Op.STORE_LOCAL, register)

    def add(self) -> "PolicyBuilder":
        return self.emit(Op.ADD)

    def subtract(self) -> "PolicyBuilder":
        return self.emit(Op.SUB)

    def multiply(self) -> "PolicyBuilder":
        return self.emit(Op.MUL)

    def divide(self) -> "PolicyBuilder":
        return self.emit(Op.DIV)

    def minimum(self) -> "PolicyBuilder":
        return self.emit(Op.MIN)

    def maximum(self) -> "PolicyBuilder":
        return self.emit(Op.MAX)

    def clamp(self, lower: float, upper: float) -> "PolicyBuilder":
        if lower > upper:
            raise ValueError("lower bound must not exceed upper bound")
        return self.constant(lower).constant(upper).emit(Op.CLAMP)

    def clamp01(self) -> "PolicyBuilder":
        return self.clamp(0, 1)

    def normalize(self, lower: float, upper: float, *, clamp: bool = True) -> "PolicyBuilder":
        """Normalize the current top-of-stack from [lower, upper] to [0, 1]."""
        if lower >= upper:
            raise ValueError("normalization requires lower < upper")
        self.constant(lower).subtract().constant(upper - lower).divide()
        return self.clamp01() if clamp else self

    def percentage(self) -> "PolicyBuilder":
        return self.constant(100).multiply()

    def greater_than(self, threshold: float) -> "PolicyBuilder":
        return self.constant(threshold).emit(Op.GT)

    def at_least(self, threshold: float) -> "PolicyBuilder":
        return self.constant(threshold).emit(Op.GTE)

    def less_than(self, threshold: float) -> "PolicyBuilder":
        return self.constant(threshold).emit(Op.LT)

    def at_most(self, threshold: float) -> "PolicyBuilder":
        return self.constant(threshold).emit(Op.LTE)

    def equals(self, value: float) -> "PolicyBuilder":
        return self.constant(value).emit(Op.EQ)

    def between(self, lower: float, upper: float) -> "PolicyBuilder":
        if lower > upper:
            raise ValueError("lower bound must not exceed upper bound")
        return self.constant(lower).constant(upper).emit(Op.BETWEEN)

    def logical_not(self) -> "PolicyBuilder":
        return self.emit(Op.NOT)

    def select(self, true_value: float, false_value: float) -> "PolicyBuilder":
        """Select constants using the condition currently on the stack."""
        return self.constant(true_value).constant(false_value).emit(Op.SELECT)

    def store_score(self) -> "PolicyBuilder":
        return self.emit(Op.STORE_SCORE)

    def store_severity(self) -> "PolicyBuilder":
        return self.emit(Op.STORE_SEVERITY)

    def store_route(self) -> "PolicyBuilder":
        return self.emit(Op.STORE_ROUTE)

    def store_suppressed(self) -> "PolicyBuilder":
        return self.emit(Op.STORE_SUPPRESS)

    def halt(self) -> "PolicyBuilder":
        return self.emit(Op.HALT)

    def build(self, *, require_outputs: bool = False) -> list[Instruction]:
        ir = list(self.instructions)
        if not ir or ir[-1].op is not Op.HALT:
            ir.append(Instruction(Op.HALT))
        analysis = analyze_ir(ir)
        if require_outputs:
            expected = {"alert_score", "severity_code", "routing_code", "suppressed"}
            missing = expected.difference(analysis.outputs_written)
            if missing:
                raise ValueError("policy does not write outputs: " + ", ".join(sorted(missing)))
        return ir


def weighted_sum(terms: Sequence[tuple[str, float]]) -> list[Instruction]:
    """Emit a weighted sum of named policy inputs.

    Weights are intentionally explicit and may be negative. At least one term is
    required. Input names are validated by the engine when the generated IR is
    analyzed.
    """
    if not terms:
        raise ValueError("weighted_sum requires at least one term")
    builder = PolicyBuilder()
    for index, (name, weight) in enumerate(terms):
        builder.input(name).constant(weight).multiply()
        if index:
            builder.add()
    return builder.instructions


def weighted_average(terms: Sequence[tuple[str, float]]) -> list[Instruction]:
    """Emit a weighted average and reject zero total weight."""
    total_weight = sum(weight for _, weight in terms)
    if not terms:
        raise ValueError("weighted_average requires at least one term")
    if total_weight == 0:
        raise ValueError("weighted_average total weight must not be zero")
    return weighted_sum(terms) + [Instruction(Op.PUSH_CONST, total_weight), Instruction(Op.DIV)]


def all_conditions(conditions: Sequence[Sequence[Instruction]]) -> list[Instruction]:
    if not conditions:
        return [Instruction(Op.PUSH_CONST, 1)]
    result: list[Instruction] = []
    for index, condition in enumerate(conditions):
        result.extend(condition)
        if index:
            result.append(Instruction(Op.AND))
    return result


def any_condition(conditions: Sequence[Sequence[Instruction]]) -> list[Instruction]:
    if not conditions:
        return [Instruction(Op.PUSH_CONST, 0)]
    result: list[Instruction] = []
    for index, condition in enumerate(conditions):
        result.extend(condition)
        if index:
            result.append(Instruction(Op.OR))
    return result


def input_at_least(name: str, threshold: float) -> list[Instruction]:
    return [
        Instruction(Op.LOAD_INPUT, name),
        Instruction(Op.PUSH_CONST, threshold),
        Instruction(Op.GTE),
    ]


def input_at_most(name: str, threshold: float) -> list[Instruction]:
    return [
        Instruction(Op.LOAD_INPUT, name),
        Instruction(Op.PUSH_CONST, threshold),
        Instruction(Op.LTE),
    ]


def input_between(name: str, lower: float, upper: float) -> list[Instruction]:
    if lower > upper:
        raise ValueError("lower bound must not exceed upper bound")
    return [
        Instruction(Op.LOAD_INPUT, name),
        Instruction(Op.PUSH_CONST, lower),
        Instruction(Op.PUSH_CONST, upper),
        Instruction(Op.BETWEEN),
    ]


def severity_bands(
    *,
    medium_score: float = 40,
    high_score: float = 65,
    critical_score: float = 85,
    low: int = 1,
    medium: int = 2,
    high: int = 3,
    critical: int = 4,
) -> list[Instruction]:
    """Map the current score value to a severity code without branching.

    The score remains consumed. The resulting severity code is left on stack.
    """
    if not (medium_score <= high_score <= critical_score):
        raise ValueError("severity thresholds must be ordered")
    return [
        Instruction(Op.STORE_LOCAL, 15),
        Instruction(Op.LOAD_LOCAL, 15),
        Instruction(Op.PUSH_CONST, critical_score),
        Instruction(Op.GTE),
        Instruction(Op.PUSH_CONST, critical),
        Instruction(Op.LOAD_LOCAL, 15),
        Instruction(Op.PUSH_CONST, high_score),
        Instruction(Op.GTE),
        Instruction(Op.PUSH_CONST, high),
        Instruction(Op.LOAD_LOCAL, 15),
        Instruction(Op.PUSH_CONST, medium_score),
        Instruction(Op.GTE),
        Instruction(Op.PUSH_CONST, medium),
        Instruction(Op.PUSH_CONST, low),
        Instruction(Op.SELECT),
        Instruction(Op.SELECT),
        Instruction(Op.SELECT),
    ]


def route_when(condition: Sequence[Instruction], true_route: int, false_route: int = 0) -> list[Instruction]:
    return list(condition) + [
        Instruction(Op.PUSH_CONST, true_route),
        Instruction(Op.PUSH_CONST, false_route),
        Instruction(Op.SELECT),
        Instruction(Op.STORE_ROUTE),
    ]


def suppress_when(condition: Sequence[Instruction]) -> list[Instruction]:
    return list(condition) + [Instruction(Op.STORE_SUPPRESS)]


def standard_alert_policy(
    terms: Sequence[tuple[str, float]],
    *,
    score_scale: float = 100,
    suppress_below: float = 15,
    default_route: int = 1,
) -> list[Instruction]:
    """Build a complete four-output policy from weighted normalized inputs."""
    if score_scale <= 0:
        raise ValueError("score_scale must be positive")

    builder = PolicyBuilder()
    builder.extend(weighted_average(terms)).constant(score_scale).multiply()
    builder.emit(Op.DUP).store_score()
    builder.emit(Op.DUP).extend(severity_bands()).store_severity()
    builder.emit(Op.DUP).constant(suppress_below).emit(Op.LT).store_suppressed()
    builder.emit(Op.DROP).constant(default_route).store_route().halt()
    return builder.build(require_outputs=True)
