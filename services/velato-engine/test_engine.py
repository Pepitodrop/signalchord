import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("velato_engine", Path(__file__).with_name("engine.py"))
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

def inputs() -> dict[str, float]:
    return {k: .5 for k in mod.INPUTS} | {"watchlist_match": 1, "novelty": .8, "entity_relevance": .9, "source_diversity": .4}

def test_default_policy_is_deterministic() -> None:
    a = mod.execute(mod.default_policy_ir(), inputs())
    b = mod.execute(mod.default_policy_ir(), inputs())
    assert a == b and 0 <= a.alert_score <= 100

def test_instruction_limit() -> None:
    try:
        mod.execute([mod.Instruction(mod.Op.PUSH_CONST, 1)] * 600, inputs(), max_instructions=10)
    except ValueError as exc:
        assert "instruction limit" in str(exc)
    else:
        raise AssertionError("expected limit")

def test_stack_underflow() -> None:
    try:
        mod.execute([mod.Instruction(mod.Op.ADD), mod.Instruction(mod.Op.HALT)], inputs())
    except ValueError as exc:
        assert "underflow" in str(exc)
    else:
        raise AssertionError("expected underflow")
