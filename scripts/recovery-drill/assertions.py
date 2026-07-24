"""Small, pure, unit-testable assertion helpers shared by the recovery-drill
workflow's Python- and Go-poison-message, transient-failure and duplicate-
suppression checks. Each function takes already-collected data (parsed JSON
from kafka_tool.py, or plain counts) and returns a list of human-readable
failure strings -- an empty list means the assertion passed. Nothing here
talks to Kafka, Postgres or Kubernetes directly.
"""

from __future__ import annotations

from typing import Any

REQUIRED_DLQ_ENVELOPE_FIELDS = (
    "origin",
    "error_type",
    "error",
    "failed_at",
    "source_topic",
    "source_partition",
    "source_offset",
    "key",
    "headers",
)


def assert_dlq_envelope(
    envelope: dict[str, Any],
    *,
    expected_origin: str,
    expected_source_topic: str,
    content_field: str,
) -> list[str]:
    """Assert a DLQ envelope (already JSON-decoded from a consumed message's
    value) carries the required source/error metadata. `content_field` is
    the field holding the original event content -- "failed_event" for the
    Python helper's envelopes, "value" for the Go helper's."""
    failures: list[str] = []
    for field in (*REQUIRED_DLQ_ENVELOPE_FIELDS, content_field):
        if field not in envelope:
            failures.append(f"dlq envelope missing field: {field}")
    if envelope.get("origin") != expected_origin:
        failures.append(f"dlq envelope origin = {envelope.get('origin')!r}, want {expected_origin!r}")
    if envelope.get("source_topic") != expected_source_topic:
        failures.append(
            f"dlq envelope source_topic = {envelope.get('source_topic')!r}, want {expected_source_topic!r}"
        )
    if not envelope.get("error_type"):
        failures.append("dlq envelope error_type is empty")
    if not envelope.get("error"):
        failures.append("dlq envelope error is empty")
    if not envelope.get("failed_at"):
        failures.append("dlq envelope failed_at is empty")
    return failures


def assert_offset_advanced_past(*, before: int, after: int, target_offset: int) -> list[str]:
    """Assert a consumer group's committed offset moved forward from `before`
    to `after`, and that `after` is past `target_offset` (i.e. the message at
    `target_offset` has been marked/committed)."""
    failures: list[str] = []
    if after <= before:
        failures.append(f"committed offset did not advance: before={before} after={after}")
    if after <= target_offset:
        failures.append(f"committed offset {after} has not passed target offset {target_offset}")
    return failures


def assert_offset_unchanged(*, before: int, after: int) -> list[str]:
    """Assert a transient failure never advanced the committed offset at all."""
    if after != before:
        return [f"committed offset advanced for a transient failure: before={before} after={after}"]
    return []


def assert_no_dlq_message(messages: list[Any]) -> list[str]:
    """Assert a transient failure never reached the DLQ."""
    if messages:
        return [f"expected no DLQ messages for a transient failure, found {len(messages)}"]
    return []


def assert_exactly_one_dlq_message(messages: list[Any]) -> list[str]:
    if len(messages) != 1:
        return [f"expected exactly one DLQ message, found {len(messages)}"]
    return []


def assert_row_count_unchanged(*, before: int, after: int, expected: int = 1) -> list[str]:
    """Assert a replayed/redelivered already-processed event did not create a
    duplicate row (§24.5's duplicate-suppression guarantee)."""
    failures: list[str] = []
    if before != expected:
        failures.append(f"row count before replay = {before}, want {expected}")
    if after != expected:
        failures.append(f"row count after replay = {after}, want {expected}")
    return failures
