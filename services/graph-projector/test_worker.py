from __future__ import annotations

import sys
from pathlib import Path
from typing import Self

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from worker import PermanentMutationError, build_statement, handle_one_message, parse_event


class FakeMessage:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def topic(self) -> str:
        return "graph.mutation-requested.v1"

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return 1

    def key(self) -> bytes | None:
        return None

    def value(self) -> bytes:
        return self._value

    def headers(self) -> None:
        return None


class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[dict] = []

    def produce(self, topic, key=None, value=None, on_delivery=None) -> None:
        self.produced.append({"topic": topic, "key": key, "value": value})
        if on_delivery is not None:
            on_delivery(None, None)

    def flush(self, timeout: float = 10.0) -> int:
        return 0


class FakeConsumer:
    def __init__(self) -> None:
        self.committed: list[object] = []

    def commit(self, message, asynchronous: bool = False) -> None:
        self.committed.append(message)


class FakeTx:
    def run(self, query: str, **params: object) -> FakeTx:
        return self

    def consume(self) -> None:
        return None


class FakeSession:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def execute_write(self, fn):
        return fn(FakeTx())


class FakeDriver:
    def session(self) -> FakeSession:
        return FakeSession()


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


def test_requires_tenant_id() -> None:
    with pytest.raises(PermanentMutationError, match="tenant_id"):
        build_statement(
            {"payload": {"mutation_type": "upsert_document", "stable_id": "document:1"}}
        )


def test_node_identity_includes_tenant_id() -> None:
    statement = build_statement(
        event({"mutation_type": "upsert_document", "stable_id": "document:1"})
    )
    assert "MERGE (n:GraphNode {tenant_id: $tenant_id, stable_id: $stable_id})" in statement.query
    assert statement.parameters["tenant_id"] == "tenant-1"


def test_relationship_endpoint_identity_includes_tenant_id() -> None:
    statement = build_statement(
        event(
            {
                "mutation_type": "link_mentions",
                "stable_id": "relationship:1",
                "from_id": "article:1",
                "to_id": "entity:1",
            }
        )
    )
    assert "MERGE (a:GraphNode {tenant_id: $tenant_id, stable_id: $from_id})" in statement.query
    assert "MERGE (b:GraphNode {tenant_id: $tenant_id, stable_id: $to_id})" in statement.query


def test_source_takedown_marks_only_tenant_scoped_source_and_articles() -> None:
    statement = build_statement(
        event(
            {
                "mutation_type": "mark_source_takedown",
                "stable_id": "source:1",
                "properties": {"reason": "contract_expired"},
            }
        )
    )

    assert (
        "MATCH (source:GraphNode {tenant_id: $tenant_id, stable_id: $stable_id})" in statement.query
    )
    assert "SET article.takedown_status = 'source_requested'" in statement.query
    assert statement.parameters["tenant_id"] == "tenant-1"


def test_parse_event_rejects_malformed_json() -> None:
    with pytest.raises(PermanentMutationError, match="valid JSON"):
        parse_event(b"{not json")


def test_parse_event_rejects_non_object_json() -> None:
    with pytest.raises(PermanentMutationError, match="JSON object"):
        parse_event(b"[]")


def test_handle_one_message_routes_permanent_failure_through_shared_helper() -> None:
    message = FakeMessage(b"{not json")
    consumer = FakeConsumer()
    producer = FakeProducer()

    handle_one_message(message, consumer, producer, FakeDriver())

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == "graph.mutation-requested.v1.dlq"
    assert consumer.committed == [message]


def test_handle_one_message_commits_after_successful_processing() -> None:
    message = FakeMessage(
        b'{"tenant_id":"tenant-1","event_id":"e-1","payload":'
        b'{"mutation_type":"upsert_document","stable_id":"document:1","properties":{}}}'
    )
    consumer = FakeConsumer()
    producer = FakeProducer()

    handle_one_message(message, consumer, producer, FakeDriver())

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == "graph.mutation-completed.v1"
    assert consumer.committed == [message]
