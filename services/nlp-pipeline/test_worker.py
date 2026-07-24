from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# worker.py does `from app import ...` (a bare sibling import): several other
# services also have their own same-named app.py, so drop any stale cached
# "app" module a previously-collected test file may have left behind, forcing
# a fresh import that resolves against this directory's sys.path entry above.
sys.modules.pop("app", None)

MODULE_PATH = Path(__file__).with_name("worker.py")
SPEC = importlib.util.spec_from_file_location("signalchord_nlp_pipeline_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)
# Prevent this directory's "app" from leaking into a later test file that
# expects a *different* same-named app.py (e.g. graph-analytics's).
sys.modules.pop("app", None)


class FakeMessage:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def topic(self) -> str:
        return "document.nlp-requested.v1"

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


def event(payload: dict) -> dict:
    return {
        "event_id": "e-1",
        "tenant_id": "tenant-1",
        "correlation_id": "corr-1",
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": payload,
    }


def test_handle_one_message_routes_oversized_inline_text_to_dlq() -> None:
    message = FakeMessage(
        json.dumps(
            event({"document_id": "doc-1", "text": "x" * (worker.MAX_TEXT_BYTES + 1)})
        ).encode()
    )
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer, storage=None)

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == worker.DLQ_TOPIC
    assert consumer.committed == [message]


def test_handle_one_message_commits_after_successful_extraction() -> None:
    message = FakeMessage(
        json.dumps(
            event(
                {
                    "document_id": "doc-1",
                    "text": (
                        "Acme Corporation announced a strategic partnership with "
                        "Northstar Labs in Berlin."
                    ),
                }
            )
        ).encode()
    )
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer, storage=None)

    published_topics = {item["topic"] for item in producer.produced}
    assert "document.nlp-completed.v1" in published_topics
    assert worker.DLQ_TOPIC not in published_topics
    assert consumer.committed == [message]
