"""Shared poison-message isolation for confluent_kafka consumers.

Generalized rule (locked in docs/specs/recovery-and-replay-hardening.md §24.6):
`ValueError` and subclasses are permanent failures -- publish the original
message plus failure metadata to `<input-topic>.dlq` and commit the offset.
Everything else is transient -- propagate uncaught so the process crash-loops
and Kubernetes restarts it, without ever committing the offset.

This module deliberately does not look at `message.error()` at all: Kafka
transport errors are the caller's responsibility to check and raise *before*
calling into `handle_message`, exactly as every worker already does. That
keeps a transport error from ever being reclassified as a poison message here.

This module is independent of worker-specific business logic: it knows
nothing about event schemas, topics beyond the one DLQ topic it is told to
use, or what `process()` actually does -- only how to classify its outcome.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from confluent_kafka import Consumer, Message, Producer

MAX_ERROR_MESSAGE_LENGTH = 500


class DlqPublishError(RuntimeError):
    """The DLQ publish for a permanent failure could not be confirmed delivered.

    Deliberately NOT a ValueError: a failure to reach the DLQ topic is itself
    a transient infrastructure problem, not evidence the message is poison.
    Raising this (rather than swallowing it) means the caller's offset is
    never committed and the process is free to crash-loop and retry, the same
    as any other transient failure.
    """


@dataclass(frozen=True)
class DlqEnvelope:
    """The structure published to `<input-topic>.dlq`. Call `.to_dict()` before
    JSON-encoding; kept as a dataclass so tests can assert on fields by name."""

    origin: str
    error_type: str
    error: str
    failed_at: str
    source_topic: str | None
    source_partition: int | None
    source_offset: int | None
    key: str | None
    key_encoding: str
    headers: list[dict[str, str]]
    failed_event: Any
    value_encoding: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "error_type": self.error_type,
            "error": self.error,
            "failed_at": self.failed_at,
            "source_topic": self.source_topic,
            "source_partition": self.source_partition,
            "source_offset": self.source_offset,
            "key": self.key,
            "key_encoding": self.key_encoding,
            "headers": self.headers,
            "failed_event": self.failed_event,
            "value_encoding": self.value_encoding,
        }


def _decode_bytes(value: bytes | None) -> tuple[str | None, str]:
    if value is None:
        return None, "utf-8"
    try:
        return value.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return base64.b64encode(value).decode("ascii"), "base64"


def _decode_headers(headers: list[tuple[str, bytes]] | None) -> list[dict[str, str]]:
    if not headers:
        return []
    decoded = []
    for name, raw_value in headers:
        value, encoding = _decode_bytes(raw_value)
        decoded.append({"name": name, "value": value or "", "encoding": encoding})
    return decoded


def build_dlq_envelope(
    message: Message,
    error: Exception,
    *,
    origin: str,
    failed_event: Any = None,
) -> DlqEnvelope:
    """Build the DLQ envelope for a message that failed permanently.

    `failed_event` lets a worker supply its own representation of "the
    original event" (e.g. an already-parsed dict) -- if omitted, the raw
    message value is used instead (decoded as UTF-8 text, or base64 if it
    isn't valid UTF-8), which is always available regardless of what the
    worker's own processing logic managed to parse before failing.
    """
    value_text, value_encoding = _decode_bytes(message.value())
    key_text, key_encoding = _decode_bytes(message.key())
    return DlqEnvelope(
        origin=origin,
        error_type=type(error).__name__,
        error=str(error)[:MAX_ERROR_MESSAGE_LENGTH],
        failed_at=datetime.now(UTC).isoformat(),
        source_topic=message.topic(),
        source_partition=message.partition(),
        source_offset=message.offset(),
        key=key_text,
        key_encoding=key_encoding,
        headers=_decode_headers(message.headers()),
        failed_event=failed_event if failed_event is not None else value_text,
        value_encoding=value_encoding,
    )


def publish_to_dlq(
    producer: Producer,
    topic: str,
    key: bytes | None,
    envelope: DlqEnvelope,
    *,
    flush_timeout: float = 10.0,
) -> None:
    """Publish `envelope` to `topic` and block until delivery is confirmed.

    Raises DlqPublishError (without ever calling the caller's commit) if
    delivery cannot be confirmed within `flush_timeout` seconds, or if the
    broker reports a delivery error -- producer delivery confirmation is
    required before the caller may commit the source offset.
    """
    delivery_error: BaseException | None = None

    def _on_delivery(err: object, _message: object) -> None:
        nonlocal delivery_error
        if err is not None:
            delivery_error = RuntimeError(str(err))

    producer.produce(
        topic,
        key=key,
        value=json.dumps(envelope.to_dict(), separators=(",", ":"), default=str).encode("utf-8"),
        on_delivery=_on_delivery,
    )
    pending = producer.flush(flush_timeout)
    if pending > 0:
        raise DlqPublishError(
            f"timed out waiting for DLQ delivery confirmation to {topic!r} "
            f"({pending} message(s) still undelivered)"
        )
    if delivery_error is not None:
        raise DlqPublishError(f"DLQ publish to {topic!r} failed: {delivery_error}")


def handle_message(
    *,
    consumer: Consumer,
    message: Message,
    producer: Producer,
    dlq_topic: str,
    process: Callable[[], None],
    origin: str,
    failed_event: Callable[[], Any] | None = None,
    dlq_key: Callable[[], bytes | None] | None = None,
    flush_timeout: float = 10.0,
) -> None:
    """Process one message, isolating a permanent failure to the DLQ.

    - `process()` runs the worker's own handling of `message`. Any
      ValueError (or subclass) it raises is treated as a permanent failure:
      the original message plus failure metadata is published to
      `dlq_topic`, confirmed delivered, and only then is the offset
      committed.
    - Any other exception from `process()` propagates out of this function
      uncaught, and the offset is never committed -- the caller's own
      poll loop is expected to let this crash the process (transient,
      matching the existing convention of every worker in this codebase).
    - If the DLQ publish itself cannot be confirmed delivered, the
      resulting DlqPublishError also propagates uncaught with no commit,
      for the same reason: an unconfirmed DLQ write is not a safely
      isolated poison message yet.
    - On success (process() returns normally), the offset is committed the
      same way it always has been.

    Kafka transport errors (`message.error()`) are NOT handled here -- the
    caller must check that and raise before ever calling this function.
    """
    try:
        process()
    except ValueError as error:
        envelope = build_dlq_envelope(
            message,
            error,
            origin=origin,
            failed_event=failed_event() if failed_event is not None else None,
        )
        key = dlq_key() if dlq_key is not None else message.key()
        publish_to_dlq(producer, dlq_topic, key, envelope, flush_timeout=flush_timeout)

    consumer.commit(message=message, asynchronous=False)
