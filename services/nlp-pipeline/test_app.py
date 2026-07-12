import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("nlp_app", Path(__file__).with_name("app.py"))
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

def test_extracts_evidence() -> None:
    result = mod.extract(mod.Document(document_id="d1", text="Acme Corporation announced a partnership in Berlin."))
    assert any(m.entity_type == "Organization" for m in result.mentions)
    assert result.claims and result.claims[0].evidence.span_hash
