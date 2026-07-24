from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
# worker.py does `from app import ...` (a bare sibling import): several other
# services also have their own same-named app.py, so drop any stale cached
# "app" module a previously-collected test file may have left behind, forcing
# a fresh import that resolves against this directory's sys.path entry above.
sys.modules.pop("app", None)
SPEC = importlib.util.spec_from_file_location(
    "signalchord_graph_analytics_worker", Path(__file__).with_name("worker.py")
)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)
# Prevent this directory's "app" from leaking into a later test file that
# expects a *different* same-named app.py (e.g. nlp-pipeline's).
sys.modules.pop("app", None)


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


def test_handle_one_message_does_not_commit_on_malformed_payload() -> None:
    # Missing "entity_id" -- a KeyError, not a ValueError, so this must stay
    # transient (no new permanent-validation rule is being invented here).
    event = {
        "tenant_id": "tenant-1",
        "event_id": "e-1",
        "correlation_id": "corr-1",
        "payload": {},
    }
    message = FakeMessage(json.dumps(event).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(KeyError):
        worker.handle_one_message(message, consumer, producer, driver=None)

    assert producer.produced == []
    assert consumer.committed == []
