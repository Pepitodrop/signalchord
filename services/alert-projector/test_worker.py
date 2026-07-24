from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
SPEC = importlib.util.spec_from_file_location(
    "signalchord_alert_projector_worker", Path(__file__).with_name("worker.py")
)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)


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


def _client(status_code: int) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"ok": status_code < 300})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_handle_one_message_commits_after_successful_projection() -> None:
    message = FakeMessage(json.dumps({"event_id": "e-1"}).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer, _client(200))

    assert producer.produced == []
    assert consumer.committed == [message]


def test_handle_one_message_does_not_commit_on_transient_http_failure() -> None:
    message = FakeMessage(json.dumps({"event_id": "e-1"}).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(httpx.HTTPStatusError):
        worker.handle_one_message(message, consumer, producer, _client(500))

    assert producer.produced == []
    assert consumer.committed == []
