from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from python_common.poison_message import (
    DlqPublishError,
    build_dlq_envelope,
    handle_message,
    publish_to_dlq,
)


class FakeMessage:
    def __init__(
        self,
        *,
        topic: str = "input-topic.v1",
        partition: int = 3,
        offset: int = 42,
        key: bytes | None = b"the-key",
        value: bytes | None = b'{"hello":"world"}',
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._key = key
        self._value = value
        self._headers = headers

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return self._partition

    def offset(self) -> int:
        return self._offset

    def key(self) -> bytes | None:
        return self._key

    def value(self) -> bytes | None:
        return self._value

    def headers(self) -> list[tuple[str, bytes]] | None:
        return self._headers


class FakeProducer:
    def __init__(self, *, deliver_ok: bool = True, pending_after_flush: int = 0) -> None:
        self.produced: list[dict[str, Any]] = []
        self.flush_calls: list[float] = []
        self._deliver_ok = deliver_ok
        self._pending_after_flush = pending_after_flush
        self._callbacks: list[Callable[[object, object], None]] = []

    def produce(
        self,
        topic: str,
        key: bytes | None = None,
        value: bytes | None = None,
        on_delivery: Callable[[object, object], None] | None = None,
    ) -> None:
        self.produced.append({"topic": topic, "key": key, "value": value})
        if on_delivery is not None:
            self._callbacks.append(on_delivery)

    def flush(self, timeout: float = 10.0) -> int:
        self.flush_calls.append(timeout)
        if self._pending_after_flush:
            return self._pending_after_flush
        for callback in self._callbacks:
            callback(None if self._deliver_ok else "simulated broker error", None)
        self._callbacks.clear()
        return 0


class FakeConsumer:
    def __init__(self) -> None:
        self.committed: list[FakeMessage] = []

    def commit(self, message: FakeMessage, asynchronous: bool = False) -> None:
        assert asynchronous is False
        self.committed.append(message)


class CustomPermanentError(ValueError):
    """A worker-defined ValueError subclass, e.g. graph-projector's PermanentMutationError."""


def test_value_error_is_permanent_publishes_to_dlq_and_commits() -> None:
    message = FakeMessage()
    producer = FakeProducer()
    consumer = FakeConsumer()

    def process() -> None:
        raise ValueError("bad payload")

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=process,
        origin="test-worker",
    )

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == "input-topic.v1.dlq"
    assert consumer.committed == [message]


def test_value_error_subclass_is_also_permanent() -> None:
    message = FakeMessage()
    producer = FakeProducer()
    consumer = FakeConsumer()

    def process() -> None:
        raise CustomPermanentError("unsupported mutation_type: bogus")

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=process,
        origin="test-worker",
    )

    assert len(producer.produced) == 1
    assert consumer.committed == [message]


def test_non_value_error_is_transient_no_commit_and_propagates() -> None:
    message = FakeMessage()
    producer = FakeProducer()
    consumer = FakeConsumer()

    def process() -> None:
        raise RuntimeError("transient provider failure")

    with pytest.raises(RuntimeError, match="transient provider failure"):
        handle_message(
            consumer=consumer,
            message=message,
            producer=producer,
            dlq_topic="input-topic.v1.dlq",
            process=process,
            origin="test-worker",
        )

    assert producer.produced == []
    assert consumer.committed == []


def test_successful_processing_commits_without_publishing_to_dlq() -> None:
    message = FakeMessage()
    producer = FakeProducer()
    consumer = FakeConsumer()
    calls: list[str] = []

    def process() -> None:
        calls.append("processed")

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=process,
        origin="test-worker",
    )

    assert calls == ["processed"]
    assert producer.produced == []
    assert consumer.committed == [message]


def test_dlq_publish_delivery_failure_raises_and_does_not_commit() -> None:
    message = FakeMessage()
    producer = FakeProducer(deliver_ok=False)
    consumer = FakeConsumer()

    def process() -> None:
        raise ValueError("bad payload")

    with pytest.raises(DlqPublishError, match="DLQ publish"):
        handle_message(
            consumer=consumer,
            message=message,
            producer=producer,
            dlq_topic="input-topic.v1.dlq",
            process=process,
            origin="test-worker",
        )

    assert consumer.committed == []


def test_dlq_publish_timeout_raises_and_does_not_commit() -> None:
    message = FakeMessage()
    producer = FakeProducer(pending_after_flush=1)
    consumer = FakeConsumer()

    def process() -> None:
        raise ValueError("bad payload")

    with pytest.raises(DlqPublishError, match="timed out"):
        handle_message(
            consumer=consumer,
            message=message,
            producer=producer,
            dlq_topic="input-topic.v1.dlq",
            process=process,
            origin="test-worker",
        )

    assert consumer.committed == []


def test_publish_to_dlq_uses_flush_for_delivery_confirmation() -> None:
    producer = FakeProducer()
    envelope = build_dlq_envelope(FakeMessage(), ValueError("x"), origin="test-worker")

    publish_to_dlq(producer, "topic.dlq", b"key", envelope, flush_timeout=3.0)

    assert producer.flush_calls == [3.0]


def test_dlq_envelope_preserves_topic_partition_offset_key_and_error_metadata() -> None:
    message = FakeMessage(
        topic="document.nlp-requested.v1",
        partition=7,
        offset=1234,
        key=b"doc-1",
        value=b'{"document_id":"doc-1"}',
        headers=[("trace-id", b"abc-123")],
    )
    error = ValueError("inline text exceeds limit")

    envelope = build_dlq_envelope(message, error, origin="nlp-pipeline")
    data = envelope.to_dict()

    assert data["source_topic"] == "document.nlp-requested.v1"
    assert data["source_partition"] == 7
    assert data["source_offset"] == 1234
    assert data["key"] == "doc-1"
    assert data["headers"] == [{"name": "trace-id", "value": "abc-123", "encoding": "utf-8"}]
    assert data["error_type"] == "ValueError"
    assert data["error"] == "inline text exceeds limit"
    assert data["origin"] == "nlp-pipeline"
    assert data["failed_event"] == '{"document_id":"doc-1"}'
    assert data.get("failed_at")


def test_dlq_envelope_accepts_a_custom_failed_event_override() -> None:
    message = FakeMessage(value=b'{"event_id":"invalid"}')
    parsed_source = {"event_id": "e-1", "payload": {"stable_id": "x"}}

    envelope = build_dlq_envelope(
        message, ValueError("bad"), origin="graph-projector", failed_event=parsed_source
    )

    assert envelope.to_dict()["failed_event"] == parsed_source


def test_dlq_envelope_handles_missing_key_and_headers() -> None:
    message = FakeMessage(key=None, headers=None)

    envelope = build_dlq_envelope(message, ValueError("bad"), origin="test-worker")
    data = envelope.to_dict()

    assert data["key"] is None
    assert data["headers"] == []


def test_dlq_envelope_base64_encodes_non_utf8_values() -> None:
    message = FakeMessage(key=b"\xff\xfe", value=b"\xff\xfe")

    envelope = build_dlq_envelope(message, ValueError("bad"), origin="test-worker")
    data = envelope.to_dict()

    assert data["key_encoding"] == "base64"
    assert data["value_encoding"] == "base64"


def test_dlq_key_override_is_used_for_the_produced_message() -> None:
    message = FakeMessage(key=b"raw-kafka-key")
    producer = FakeProducer()
    consumer = FakeConsumer()

    def process() -> None:
        raise ValueError("bad")

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=process,
        origin="test-worker",
        dlq_key=lambda: b"business-key",
    )

    assert producer.produced[0]["key"] == b"business-key"


def test_default_dlq_key_reuses_the_original_message_key() -> None:
    message = FakeMessage(key=b"raw-kafka-key")
    producer = FakeProducer()
    consumer = FakeConsumer()

    def process() -> None:
        raise ValueError("bad")

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=process,
        origin="test-worker",
    )

    assert producer.produced[0]["key"] == b"raw-kafka-key"


def test_failed_event_callable_is_only_invoked_on_permanent_failure() -> None:
    message = FakeMessage()
    producer = FakeProducer()
    consumer = FakeConsumer()
    calls: list[str] = []

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic="input-topic.v1.dlq",
        process=lambda: None,
        origin="test-worker",
        failed_event=lambda: calls.append("built") or {},
    )

    assert calls == []
