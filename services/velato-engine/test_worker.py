from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
SPEC = importlib.util.spec_from_file_location(
    "signalchord_velato_engine_worker", Path(__file__).with_name("worker.py")
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


def _inputs() -> dict:
    return {key: 0.5 for key in worker.engine.INPUTS}


def _event() -> dict:
    return {
        "tenant_id": "tenant-1",
        "event_id": "e-1",
        "correlation_id": "corr-1",
        "idempotency_key": "idem-1",
        "payload": {
            "policy_id": "default-watchlist-novelty",
            "policy_version_id": "v1",
            "inputs": _inputs(),
        },
    }


def test_handle_one_message_commits_after_successful_evaluation() -> None:
    policy_ir = worker.engine.default_policy_ir()
    message = FakeMessage(json.dumps(_event()).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(
        message,
        consumer,
        producer,
        policy_ir,
        "fallback-rules",
        None,
        worker.engine.ir_sha256(policy_ir),
        worker.engine.analyze_ir(policy_ir).model_dump(),
    )

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == "alert.created.v1"
    assert consumer.committed == [message]


def test_handle_one_message_does_not_commit_on_malformed_payload() -> None:
    policy_ir = worker.engine.default_policy_ir()
    bad_event = _event()
    del bad_event["payload"]["inputs"]
    message = FakeMessage(json.dumps(bad_event).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(KeyError):
        worker.handle_one_message(
            message,
            consumer,
            producer,
            policy_ir,
            "fallback-rules",
            None,
            worker.engine.ir_sha256(policy_ir),
            worker.engine.analyze_ir(policy_ir).model_dump(),
        )

    assert producer.produced == []
    assert consumer.committed == []
