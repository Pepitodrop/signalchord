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


def test_checked_in_midi_matches_fallback_policy() -> None:
    policy_path = (
        Path(__file__).parents[2]
        / "velato"
        / "programs"
        / "default-watchlist-novelty-v1.mid"
    )
    midi_ir = mod.compile_notes(mod.parse_midi(policy_path.read_bytes()))
    assert mod.execute(midi_ir, inputs()) == mod.execute(mod.default_policy_ir(), inputs())


def test_instruction_limit() -> None:
    try:
        mod.execute(
            [mod.Instruction(mod.Op.PUSH_CONST, 1)] * 600,
            inputs(),
            max_instructions=10,
        )
    except ValueError as exc:
        assert "instruction limit" in str(exc)
    else:
        raise AssertionError("expected limit")


def test_stack_underflow() -> None:
    try:
        mod.execute(
            [mod.Instruction(mod.Op.ADD), mod.Instruction(mod.Op.HALT)], inputs()
        )
    except ValueError as exc:
        assert "underflow" in str(exc)
    else:
        raise AssertionError("expected underflow")


def test_invalid_input_operand_is_rejected() -> None:
    notes = [mod.MidiNote(60, 64), mod.MidiNote(62, 127)]
    try:
        mod.compile_notes(notes)
    except ValueError as exc:
        assert "input register" in str(exc)
    else:
        raise AssertionError("expected invalid operand")
