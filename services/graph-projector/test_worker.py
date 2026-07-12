from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from worker import PermanentMutationError, build_statement


def event(payload: dict) -> dict:
    return {"tenant_id": "tenant-1", "payload": payload}


def test_builds_idempotent_node_upsert() -> None:
    statement = build_statement(
        event(
            {
                "mutation_type": "upsert_document",
                "stable_id": "document:1",
                "properties": {"title": "Example"},
            }
        )
    )
    assert "MERGE (n:GraphNode" in statement.query
    assert "SET n:Document" in statement.query
    assert statement.parameters["properties"]["tenant_id"] == "tenant-1"


def test_builds_allowlisted_relationship() -> None:
    statement = build_statement(
        event(
            {
                "mutation_type": "link_partnered_with",
                "stable_id": "relationship:1",
                "from_id": "company:acme",
                "to_id": "company:globex",
                "properties": {"confidence": 0.9},
            }
        )
    )
    assert "[r:PARTNERED_WITH" in statement.query
    assert statement.parameters["from_id"] == "company:acme"


def test_rejects_dynamic_relationship_type() -> None:
    with pytest.raises(PermanentMutationError, match="unsupported mutation_type"):
        build_statement(
            event(
                {
                    "mutation_type": "link_DELETE_everything",
                    "stable_id": "relationship:bad",
                    "from_id": "a",
                    "to_id": "b",
                }
            )
        )


def test_rejects_unknown_entity_type() -> None:
    with pytest.raises(PermanentMutationError, match="unsupported entity_type"):
        build_statement(
            event(
                {
                    "mutation_type": "upsert_entity",
                    "stable_id": "entity:1",
                    "entity_type": "ArbitraryLabel",
                }
            )
        )
