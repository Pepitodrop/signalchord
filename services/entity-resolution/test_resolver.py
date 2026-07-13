import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("entity_resolver", Path(__file__).with_name("resolver.py"))
resolver = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = resolver
spec.loader.exec_module(resolver)


def test_exact_alias_is_accepted() -> None:
    result = resolver.resolve("m1", "Acme Corporation", {"acme corporation": "company:acme"})
    assert result.accepted_entity_id == "company:acme"
    assert result.requires_review is False


def test_low_confidence_person_remains_candidate() -> None:
    result = resolver.resolve_mention(
        {
            "mention_id": "m2",
            "document_id": "doc:1",
            "text": "Jane Example",
            "entity_type": "Person",
            "confidence": 0.82,
            "evidence": {
                "evidence_id": "ev:1",
                "document_id": "doc:1",
                "start_offset": 0,
                "end_offset": 12,
                "span_hash": "abc",
            },
        }
    )
    assert result["status"] == "candidate"
    assert result["requires_review"] is True
