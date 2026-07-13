import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("nlp_app", Path(__file__).with_name("app.py"))
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_extracts_evidence_claims_topics_and_relationships() -> None:
    result = mod.extract(
        mod.Document(
            document_id="d1",
            text=(
                "Acme Corporation announced a strategic partnership with Northstar Labs in Berlin. "
                "Jordan Meyer said the companies plan to build a logistics platform."
            ),
        )
    )
    assert any(mention.entity_type == "Company" for mention in result.mentions)
    assert any(mention.entity_type == "Organization" for mention in result.mentions)
    assert any(mention.entity_type == "Location" for mention in result.mentions)
    assert result.claims and result.claims[0].evidence.span_hash
    assert any(relation.predicate == "PARTNERED_WITH" for relation in result.relations)
    assert "partnerships" in result.topics
    assert len(result.embedding) == 32


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    first = mod.hash_embedding("Acme builds software")
    second = mod.hash_embedding("Acme builds software")
    assert first == second
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-4
