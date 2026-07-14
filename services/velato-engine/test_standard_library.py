import importlib.util
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).parent
sys.path.insert(0, str(SERVICE_DIR))

engine_spec = importlib.util.spec_from_file_location("engine", SERVICE_DIR / "engine.py")
engine = importlib.util.module_from_spec(engine_spec)
assert engine_spec and engine_spec.loader
sys.modules[engine_spec.name] = engine
engine_spec.loader.exec_module(engine)

stdlib_spec = importlib.util.spec_from_file_location(
    "standard_library", SERVICE_DIR / "standard_library.py"
)
stdlib = importlib.util.module_from_spec(stdlib_spec)
assert stdlib_spec and stdlib_spec.loader
sys.modules[stdlib_spec.name] = stdlib
stdlib_spec.loader.exec_module(stdlib)


def policy_inputs(**overrides: float) -> dict[str, float]:
    values = {name: 0.0 for name in engine.INPUTS}
    values.update(overrides)
    return values


def execute_expression(instructions, inputs=None):
    ir = list(instructions) + [
        engine.Instruction(engine.Op.STORE_SCORE),
        engine.Instruction(engine.Op.PUSH_CONST, 0),
        engine.Instruction(engine.Op.STORE_SEVERITY),
        engine.Instruction(engine.Op.PUSH_CONST, 0),
        engine.Instruction(engine.Op.STORE_ROUTE),
        engine.Instruction(engine.Op.PUSH_CONST, 0),
        engine.Instruction(engine.Op.STORE_SUPPRESS),
        engine.Instruction(engine.Op.HALT),
    ]
    return engine.execute(ir, inputs or policy_inputs())


def test_weighted_sum() -> None:
    result = execute_expression(
        stdlib.weighted_sum([("novelty", 50), ("source_trust", 25)]),
        policy_inputs(novelty=1, source_trust=0.4),
    )
    assert result.alert_score == 60


def test_weighted_average() -> None:
    result = execute_expression(
        stdlib.weighted_average([("novelty", 3), ("source_trust", 1)]),
        policy_inputs(novelty=1, source_trust=0),
    )
    assert result.alert_score == 1


def test_boolean_condition_composition() -> None:
    conditions = stdlib.all_conditions(
        [
            stdlib.input_at_least("source_trust", 0.7),
            stdlib.input_at_most("contradiction_count", 1),
            stdlib.input_between("novelty", 0.5, 1.0),
        ]
    )
    result = execute_expression(
        conditions,
        policy_inputs(source_trust=0.8, contradiction_count=1, novelty=0.6),
    )
    assert result.alert_score == 1


def test_empty_all_and_any_have_identity_values() -> None:
    assert execute_expression(stdlib.all_conditions([])).alert_score == 1
    assert execute_expression(stdlib.any_condition([])).alert_score == 0


def test_severity_bands() -> None:
    for score, expected in [(20, 1), (40, 2), (65, 3), (85, 4), (100, 4)]:
        ir = [engine.Instruction(engine.Op.PUSH_CONST, score)]
        ir += stdlib.severity_bands()
        ir += [
            engine.Instruction(engine.Op.PUSH_CONST, 0),
            engine.Instruction(engine.Op.STORE_SCORE),
            engine.Instruction(engine.Op.STORE_SEVERITY),
            engine.Instruction(engine.Op.PUSH_CONST, 0),
            engine.Instruction(engine.Op.STORE_ROUTE),
            engine.Instruction(engine.Op.PUSH_CONST, 0),
            engine.Instruction(engine.Op.STORE_SUPPRESS),
            engine.Instruction(engine.Op.HALT),
        ]
        assert engine.execute(ir, policy_inputs()).severity_code == expected


def test_severity_bands_preserves_caller_local_registers() -> None:
    ir = [
        engine.Instruction(engine.Op.PUSH_CONST, 123),
        engine.Instruction(engine.Op.STORE_LOCAL, 15),
        engine.Instruction(engine.Op.PUSH_CONST, 70),
        *stdlib.severity_bands(),
        engine.Instruction(engine.Op.STORE_SEVERITY),
        engine.Instruction(engine.Op.LOAD_LOCAL, 15),
        engine.Instruction(engine.Op.STORE_ROUTE),
        engine.Instruction(engine.Op.PUSH_CONST, 0),
        engine.Instruction(engine.Op.STORE_SCORE),
        engine.Instruction(engine.Op.PUSH_CONST, 0),
        engine.Instruction(engine.Op.STORE_SUPPRESS),
        engine.Instruction(engine.Op.HALT),
    ]

    result = engine.execute(ir, policy_inputs())
    assert result.severity_code == 3
    assert result.routing_code == 123


def test_standard_alert_policy_writes_all_outputs() -> None:
    ir = stdlib.standard_alert_policy(
        [
            ("watchlist_match", 4),
            ("novelty", 3),
            ("entity_relevance", 2),
            ("source_trust", 1),
        ],
        suppress_below=15,
        default_route=7,
    )
    analysis = engine.analyze_ir(ir)
    assert set(analysis.outputs_written) == {
        "alert_score",
        "severity_code",
        "routing_code",
        "suppressed",
    }

    result = engine.execute(
        ir,
        policy_inputs(
            watchlist_match=1,
            novelty=0.8,
            entity_relevance=0.9,
            source_trust=0.7,
        ),
    )
    assert result.alert_score == 89
    assert result.severity_code == 4
    assert result.routing_code == 7
    assert not result.suppressed


def test_standard_alert_policy_suppresses_low_score() -> None:
    ir = stdlib.standard_alert_policy([("novelty", 1)], suppress_below=20)
    result = engine.execute(ir, policy_inputs(novelty=0.1))
    assert result.alert_score == 10
    assert result.severity_code == 1
    assert result.suppressed


def test_builder_normalize_and_clamp() -> None:
    builder = stdlib.PolicyBuilder()
    ir = (
        builder.input("corroboration_count")
        .normalize(0, 10)
        .percentage()
        .store_score()
        .constant(1)
        .store_severity()
        .constant(2)
        .store_route()
        .constant(0)
        .store_suppressed()
        .halt()
        .build(require_outputs=True)
    )
    result = engine.execute(ir, policy_inputs(corroboration_count=15))
    assert result.alert_score == 100


def test_invalid_macro_arguments_are_rejected() -> None:
    for callback in (
        lambda: stdlib.weighted_sum([]),
        lambda: stdlib.weighted_average([("novelty", 0)]),
        lambda: stdlib.PolicyBuilder().constant(1).normalize(2, 2),
        lambda: stdlib.severity_bands(medium_score=80, high_score=50),
    ):
        try:
            callback()
        except ValueError:
            pass
        else:
            raise AssertionError("expected invalid macro arguments to be rejected")
