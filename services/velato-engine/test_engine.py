import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "velato_engine", Path(__file__).with_name("engine.py")
)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def inputs() -> dict[str, float]:
    return {key: 0.5 for key in mod.INPUTS} | {
        "watchlist_match": 1,
        "novelty": 0.8,
        "entity_relevance": 0.9,
        "source_diversity": 0.4,
    }


def test_default_policy_is_deterministic() -> None:
    first = mod.execute(mod.default_policy_ir(), inputs())
    second = mod.execute(mod.default_policy_ir(), inputs())
    assert first == second
    assert first.alert_score == 84
    assert first.severity_code == 2
    assert first.routing_code == 1
    assert not first.suppressed
    assert first.max_stack_depth == 3


def test_checked_in_midi_matches_fallback_policy() -> None:
    policy_path = (
        Path(__file__).parents[2]
        / "velato"
        / "programs"
        / "default-watchlist-novelty-v1.mid"
    )
    midi_ir = mod.compile_notes(mod.parse_midi(policy_path.read_bytes()))
    assert mod.execute(midi_ir, inputs()) == mod.execute(mod.default_policy_ir(), inputs())


def test_extended_numeric_boolean_and_local_registers() -> None:
    ir = [
        mod.Instruction(mod.Op.PUSH_CONST, 9),
        mod.Instruction(mod.Op.SQRT),
        mod.Instruction(mod.Op.STORE_LOCAL, 0),
        mod.Instruction(mod.Op.LOAD_LOCAL, 0),
        mod.Instruction(mod.Op.PUSH_CONST, 2),
        mod.Instruction(mod.Op.POW),
        mod.Instruction(mod.Op.PUSH_CONST, 8),
        mod.Instruction(mod.Op.GTE),
        mod.Instruction(mod.Op.PUSH_CONST, 1),
        mod.Instruction(mod.Op.AND),
        mod.Instruction(mod.Op.PUSH_CONST, 90),
        mod.Instruction(mod.Op.PUSH_CONST, 10),
        mod.Instruction(mod.Op.SELECT),
        mod.Instruction(mod.Op.STORE_SCORE),
        mod.Instruction(mod.Op.HALT),
    ]
    result = mod.execute(ir, inputs())
    assert result.alert_score == 90


def test_stack_operations() -> None:
    ir = [
        mod.Instruction(mod.Op.PUSH_CONST, 4),
        mod.Instruction(mod.Op.DUP),
        mod.Instruction(mod.Op.ADD),
        mod.Instruction(mod.Op.PUSH_CONST, 2),
        mod.Instruction(mod.Op.SWAP),
        mod.Instruction(mod.Op.SUB),
        mod.Instruction(mod.Op.STORE_SCORE),
        mod.Instruction(mod.Op.HALT),
    ]
    assert mod.execute(ir, inputs()).alert_score == 0


def test_midi_banks_compile() -> None:
    notes = [
        mod.MidiNote(60, 64, 0),
        mod.MidiNote(61, 10, 0),
        mod.MidiNote(71, 64, 1),
        mod.MidiNote(65, 1, 3),
        mod.MidiNote(64, 1, 3),
        mod.MidiNote(68, 64, 0),
        mod.MidiNote(60, 64, 0),
    ]
    ir = mod.compile_notes(notes)
    assert [instruction.op for instruction in ir] == [
        mod.Op.PUSH_CONST,
        mod.Op.SQRT,
        mod.Op.STORE_LOCAL,
        mod.Op.LOAD_LOCAL,
        mod.Op.STORE_SCORE,
        mod.Op.HALT,
    ]
    assert mod.execute(ir, inputs()).alert_score == 3


def test_assembly_and_midi_round_trip() -> None:
    source = """
    # Extended policy
    PUSH_CONST 64
    STORE_LOCAL 2
    LOAD_LOCAL 2
    PUSH_CONST 0
    PUSH_CONST 100
    CLAMP
    STORE_SCORE
    PUSH_CONST 1
    STORE_SEVERITY
    PUSH_CONST 0
    STORE_ROUTE
    PUSH_CONST 0
    STORE_SUPPRESS
    HALT
    """
    ir = mod.parse_assembly(source)
    midi = mod.encode_midi(ir)
    round_trip = mod.compile_notes(mod.parse_midi(midi))
    assert mod.serialize_ir(round_trip) == mod.serialize_ir(ir)
    assert mod.execute(round_trip, inputs()).alert_score == 64


def test_static_analysis_and_errors() -> None:
    analysis = mod.analyze_ir(mod.default_policy_ir())
    assert set(analysis.required_inputs) == {
        "watchlist_match",
        "novelty",
        "entity_relevance",
        "source_diversity",
    }
    assert analysis.outputs_written == list(mod.OUTPUTS)

    cases = [
        (
            [mod.Instruction(mod.Op.ADD), mod.Instruction(mod.Op.HALT)],
            "static stack underflow",
        ),
        (
            [
                mod.Instruction(mod.Op.PUSH_CONST, 1),
                mod.Instruction(mod.Op.PUSH_CONST, 0),
                mod.Instruction(mod.Op.DIV),
                mod.Instruction(mod.Op.HALT),
            ],
            "division by zero",
        ),
        (
            [
                mod.Instruction(mod.Op.PUSH_CONST, -1),
                mod.Instruction(mod.Op.SQRT),
                mod.Instruction(mod.Op.HALT),
            ],
            "square root",
        ),
    ]
    for ir, expected in cases:
        try:
            mod.execute(ir, inputs())
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"expected {expected}")


def test_non_finite_input_rejected() -> None:
    invalid = inputs() | {"novelty": float("inf")}
    try:
        mod.execute(mod.default_policy_ir(), invalid)
    except ValueError as exc:
        assert "must be finite" in str(exc)
    else:
        raise AssertionError("expected non-finite rejection")


def test_unsupported_instruction_bank_rejected() -> None:
    notes = [mod.MidiNote(60, 64), mod.MidiNote(61, 64, 9)]
    try:
        mod.compile_notes(notes)
    except ValueError as exc:
        assert "instruction bank" in str(exc)
    else:
        raise AssertionError("expected unsupported bank")
