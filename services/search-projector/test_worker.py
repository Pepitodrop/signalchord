from __future__ import annotations

import importlib.util
import json
from io import BytesIO
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("worker.py")
SPEC = importlib.util.spec_from_file_location("signalchord_search_projector_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)


class FakeSearchClient:
    def __init__(self):
        self.indexed: list[dict] = []
        self.deleted: list[dict] = []

    def index(self, **kwargs):
        self.indexed.append(kwargs)

    def delete_by_query(self, **kwargs):
        self.deleted.append(kwargs)


class FakeStorage:
    def get_object(self, Bucket: str, Key: str):
        assert Bucket == "raw-documents"
        assert Key == "tenant-a/doc.txt"
        return {"Body": BytesIO(b"tenant-a article body")}


class FakeMessage:
    def __init__(self, value: bytes, topic: str = "document.normalized.v1") -> None:
        self._value = value
        self._topic = topic

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return 1

    def key(self):
        return None

    def value(self) -> bytes:
        return self._value

    def headers(self):
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


def test_document_projection_uses_tenant_prefixed_id_and_body_filter_field() -> None:
    client = FakeSearchClient()
    event = {
        "event_type": "document.normalized.v1",
        "tenant_id": "tenant-a",
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": {
            "document_id": "doc-1",
            "source_id": "source-1",
            "clean_text_object_uri": "s3://raw-documents/tenant-a/doc.txt",
            "title": "Tenant article",
            "canonical_url": "https://tenant-a.example/article",
        },
    }

    worker.project(client, FakeStorage(), event)

    assert len(client.indexed) == 1
    indexed = client.indexed[0]
    assert indexed["index"] == "signalchord-articles"
    assert indexed["id"] == "tenant-a:doc-1"
    assert indexed["refresh"] is False
    assert indexed["body"]["tenant_id"] == "tenant-a"
    assert indexed["body"]["document_id"] == "doc-1"
    assert indexed["body"]["source_id"] == "source-1"


def test_source_takedown_deletes_only_matching_tenant_source_articles() -> None:
    client = FakeSearchClient()

    worker.project(
        client,
        None,
        {
            "event_type": "source.takedown.requested.v1",
            "tenant_id": "tenant-a",
            "payload": {"source_id": "source-1"},
        },
    )

    assert client.deleted == [
        {
            "index": "signalchord-articles",
            "body": {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"tenant_id": "tenant-a"}},
                            {"term": {"source_id": "source-1"}},
                        ]
                    }
                }
            },
            "refresh": True,
            "conflicts": "proceed",
        }
    ]


def test_entity_and_claim_projection_use_tenant_prefixed_ids() -> None:
    client = FakeSearchClient()

    worker.project(
        client,
        None,
        {
            "event_type": "entity.resolved.v1",
            "tenant_id": "tenant-a",
            "payload": {
                "entity_id": "entity-1",
                "display_name": "Entity",
                "entity_type": "Organization",
                "confidence": 0.9,
                "status": "resolved",
            },
        },
    )
    worker.project(
        client,
        None,
        {
            "event_type": "claim.clustered.v1",
            "tenant_id": "tenant-a",
            "payload": {
                "claim_id": "claim-1",
                "cluster_id": "cluster-1",
                "proposition": "A claim",
                "stance": "supporting",
                "confidence": 0.8,
            },
        },
    )

    assert [item["id"] for item in client.indexed] == ["tenant-a:entity-1", "tenant-a:claim-1"]
    assert all(item["body"]["tenant_id"] == "tenant-a" for item in client.indexed)


class FakeOversizedStorage:
    def get_object(self, Bucket: str, Key: str):
        return {"Body": BytesIO(b"x" * (worker.MAX_TEXT_BYTES + 1))}


def test_handle_one_message_routes_oversized_document_to_its_source_topic_dlq() -> None:
    client = FakeSearchClient()
    producer = FakeProducer()
    consumer = FakeConsumer()
    event = {
        "event_type": "document.normalized.v1",
        "tenant_id": "tenant-a",
        "payload": {
            "document_id": "doc-1",
            "clean_text_object_uri": "s3://raw-documents/tenant-a/doc.txt",
        },
    }
    message = FakeMessage(json.dumps(event).encode(), topic="document.normalized.v1")

    worker.handle_one_message(message, consumer, producer, client, FakeOversizedStorage())

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == "document.normalized.v1.dlq"
    assert consumer.committed == [message]


def test_handle_one_message_commits_after_successful_processing() -> None:
    client = FakeSearchClient()
    producer = FakeProducer()
    consumer = FakeConsumer()
    event = {
        "event_type": "entity.resolved.v1",
        "tenant_id": "tenant-a",
        "payload": {
            "entity_id": "entity-1",
            "display_name": "Entity",
            "entity_type": "Organization",
            "confidence": 0.9,
            "status": "resolved",
        },
    }
    message = FakeMessage(json.dumps(event).encode(), topic="entity.resolved.v1")

    worker.handle_one_message(message, consumer, producer, client, None)

    assert producer.produced == []
    assert consumer.committed == [message]
    assert len(client.indexed) == 1
