import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("claim_engine", Path(__file__).with_name("engine.py"))
engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


def test_normalization_is_deterministic() -> None:
    assert engine.normalize_claim("Acme announced a partnership.") == "acme announced a partnership"
    assert engine.cluster_claim("Acme announced a partnership.") == engine.cluster_claim("ACME announced a partnership")


def test_denial_has_negative_stance() -> None:
    assert engine.cluster_claim("Acme denied the report.").stance == "negative"
