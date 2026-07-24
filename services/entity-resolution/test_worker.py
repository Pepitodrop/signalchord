from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
SPEC = importlib.util.spec_from_file_location(
    "signalchord_entity_resolution_worker", Path(__file__).with_name("worker.py")
)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)


class FakeMessage:
    def __init__(self, value: bytes, topic: str) -> None:
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


def _mention_event() -> dict:
    return {
        "tenant_id": "tenant-1",
        "event_id": "e-1",
        "correlation_id": "corr-1",
        "occurred_at": "2026-01-01T00:00:00Z",
        "event_type": "entity.mention-extracted.v1",
        "payload": {
            "mention_id": "m-1",
            "document_id": "doc-1",
            "text": "Acme Corporation",
            "entity_type": "Company",
            "confidence": 0.95,
            "evidence": {
                "evidence_id": "ev-1",
                "document_id": "doc-1",
                "start_offset": 0,
                "end_offset": 16,
                "span_hash": "abc123",
            },
        },
    }


def test_handle_one_message_commits_after_successful_resolution() -> None:
    message = FakeMessage(
        json.dumps(_mention_event()).encode(), topic="entity.mention-extracted.v1"
    )
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer)

    published_topics = {item["topic"] for item in producer.produced}
    assert "entity.resolved.v1" in published_topics
    assert consumer.committed == [message]


def test_handle_one_message_does_not_commit_on_malformed_payload() -> None:
    bad_event = _mention_event()
    del bad_event["payload"]["mention_id"]
    message = FakeMessage(json.dumps(bad_event).encode(), topic="entity.mention-extracted.v1")
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(KeyError):
        worker.handle_one_message(message, consumer, producer)

    assert producer.produced == []
    assert consumer.committed == []
