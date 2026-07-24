from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
# worker.py does `from engine import cluster_claim` (a bare sibling import):
# velato-engine also has its own same-named engine.py, so drop any stale
# cached "engine" module a previously-collected test file may have left
# behind, forcing a fresh import against this directory's sys.path entry.
sys.modules.pop("engine", None)
SPEC = importlib.util.spec_from_file_location(
    "signalchord_claim_intelligence_worker", Path(__file__).with_name("worker.py")
)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)
# Prevent this directory's "engine" from leaking into a later test file that
# expects a *different* same-named engine.py (velato-engine's).
sys.modules.pop("engine", None)


class FakeMessage:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def topic(self) -> str:
        return worker.INPUT_TOPIC

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


def _claim_event() -> dict:
    return {
        "tenant_id": "tenant-1",
        "event_id": "e-1",
        "correlation_id": "corr-1",
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": {
            "claim_id": "claim-1",
            "document_id": "doc-1",
            "proposition": "Acme acquired Globex",
            "confidence": 0.9,
            "evidence": {
                "evidence_id": "ev-1",
                "document_id": "doc-1",
                "start_offset": 0,
                "end_offset": 20,
                "span_hash": "abc123",
            },
        },
    }


def test_handle_one_message_commits_after_successful_clustering() -> None:
    message = FakeMessage(json.dumps(_claim_event()).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer)

    published_topics = {item["topic"] for item in producer.produced}
    assert "claim.clustered.v1" in published_topics
    assert consumer.committed == [message]


def test_handle_one_message_does_not_commit_on_malformed_payload() -> None:
    bad_event = _claim_event()
    del bad_event["payload"]["proposition"]
    message = FakeMessage(json.dumps(bad_event).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(KeyError):
        worker.handle_one_message(message, consumer, producer)

    assert producer.produced == []
    assert consumer.committed == []
