import importlib.util
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "velato_showcase_engine", Path(__file__).with_name("engine.py")
)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

PROGRAM_DIRECTORY = Path(__file__).parents[2] / "velato" / "programs"
BASE_INPUTS = {name: 0.5 for name in mod.INPUTS}

CASES = (
    (
        "watchlist-privateer.vasm",
        {
            "watchlist_match": 1,
            "recency": 0.9,
            "corroboration_count": 3,
            "source_trust": 0.8,
            "contradiction_count": 0,
        },
        (94, 4, 7, False),
    ),
    (
        "city-waltz.vasm",
        {
            "geographic_relevance": 0.9,
            "entity_relevance": 0.8,
            "source_diversity": 0.8,
            "source_trust": 0.8,
            "recency": 0.7,
        },
        (82, 4, 4, False),
    ),
    (
        "contradiction-canon.vasm",
        {
            "contradiction_count": 3,
            "novelty": 0.7,
            "watchlist_match": 1,
            "source_diversity": 0.8,
            "source_trust": 0.7,
            "corroboration_count": 2,
        },
        (80, 4, 5, False),
    ),
    (
        "source-trust-nocturne.vasm",
        {
            "source_trust": 0.9,
            "corroboration_count": 4,
            "source_diversity": 0.8,
            "recency": 0.7,
        },
        (89, 4, 2, False),
    ),
    (
        "novelty-rondo.vasm",
        {
            "novelty": 0.95,
            "recency": 0.9,
            "entity_relevance": 0.8,
            "graph_centrality": 0.7,
            "watchlist_match": 0,
        },
        (87, 4, 3, False),
    ),
    (
        "live-graph-minute.vasm",
        {
            "graph_centrality": 0.8,
            "novelty": 0.9,
            "recency": 0.8,
            "source_diversity": 0.7,
            "source_trust": 0.9,
            "contradiction_count": 0,
        },
        (80, 3, 6, False),
    ),
)


@pytest.mark.parametrize(("filename", "overrides", "expected"), CASES)
def test_showcase_program_is_functional_midi_policy(
    filename: str,
    overrides: dict[str, float],
    expected: tuple[int, int, int, bool],
) -> None:
    source = (PROGRAM_DIRECTORY / filename).read_text(encoding="utf-8")
    assembly_ir = mod.parse_assembly(source)
    analysis = mod.analyze_ir(assembly_ir)

    assert analysis.outputs_written == list(mod.OUTPUTS)
    assert analysis.final_stack_depth == 0
    assert not analysis.warnings

    midi = mod.encode_midi(assembly_ir)
    midi_ir = mod.compile_notes(mod.parse_midi(midi))
    assert mod.serialize_ir(midi_ir) == mod.serialize_ir(assembly_ir)

    result = mod.execute(midi_ir, BASE_INPUTS | overrides)
    assert (
        result.alert_score,
        result.severity_code,
        result.routing_code,
        result.suppressed,
    ) == expected


def test_live_graph_minute_has_exactly_one_hundred_executable_instructions() -> None:
    source = (PROGRAM_DIRECTORY / "live-graph-minute.vasm").read_text(encoding="utf-8")
    assembly_ir = mod.parse_assembly(source)

    assert len(assembly_ir) == 100
