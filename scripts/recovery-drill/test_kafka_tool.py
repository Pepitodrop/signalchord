from __future__ import annotations

import pytest

import kafka_tool


class FakeMessage:
    def __init__(self, *, topic, partition, offset, key, value, headers=None):
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._key = key
        self._value = value
        self._headers = headers

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def key(self):
        return self._key

    def value(self):
        return self._value

    def headers(self):
        return self._headers


def test_parse_headers_splits_key_value_pairs() -> None:
    headers = kafka_tool.parse_headers(["trace-id=abc-123", "origin=drill"])
    assert headers == [("trace-id", b"abc-123"), ("origin", b"drill")]


def test_parse_headers_handles_value_containing_equals() -> None:
    headers = kafka_tool.parse_headers(["query=a=b=c"])
    assert headers == [("query", b"a=b=c")]


def test_parse_headers_rejects_malformed_pair() -> None:
    with pytest.raises(ValueError, match="malformed header"):
        kafka_tool.parse_headers(["no-equals-sign"])


def test_parse_headers_none_is_empty() -> None:
    assert kafka_tool.parse_headers(None) == []


def test_decode_optional_handles_none_and_bytes() -> None:
    assert kafka_tool.decode_optional(None) is None
    assert kafka_tool.decode_optional(b"hello") == "hello"


def test_format_message_decodes_key_value_and_headers() -> None:
    message = FakeMessage(
        topic="alert.created.v1.dlq",
        partition=0,
        offset=7,
        key=b"alert-1",
        value=b'{"error_type":"ValueError"}',
        headers=[("origin", b"graph-projector")],
    )

    formatted = kafka_tool.format_message(message)

    assert formatted == {
        "topic": "alert.created.v1.dlq",
        "partition": 0,
        "offset": 7,
        "key": "alert-1",
        "value": '{"error_type":"ValueError"}',
        "headers": {"origin": "graph-projector"},
    }


def test_format_message_handles_missing_key_and_headers() -> None:
    message = FakeMessage(topic="t", partition=0, offset=1, key=None, value=b"v", headers=None)

    formatted = kafka_tool.format_message(message)

    assert formatted["key"] is None
    assert formatted["headers"] == {}


def test_format_offsets_merges_committed_and_watermarks() -> None:
    committed = {"alert.created.v1-0": 12}
    watermarks = {"alert.created.v1-0": (0, 15)}

    merged = kafka_tool.format_offsets(committed, watermarks)

    assert merged == {
        "alert.created.v1-0": {
            "committed_offset": 12,
            "log_start_offset": 0,
            "log_end_offset": 15,
        }
    }


def test_format_offsets_reports_none_for_uncommitted_partition() -> None:
    merged = kafka_tool.format_offsets({}, {"t-0": (0, 3)})

    assert merged["t-0"]["committed_offset"] is None
    assert merged["t-0"]["log_end_offset"] == 3


def test_build_parser_requires_bootstrap_server_and_subcommand() -> None:
    parser = kafka_tool.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_build_parser_produce_defaults() -> None:
    parser = kafka_tool.build_parser()
    args = parser.parse_args(
        ["--bootstrap-server", "kafka:9092", "produce", "--topic", "t", "--key", "k", "--value", "v"]
    )
    assert args.command == "produce"
    assert args.topic == "t"
    assert args.timeout_seconds == 10.0


def test_build_parser_consume_defaults() -> None:
    parser = kafka_tool.build_parser()
    args = parser.parse_args(
        ["--bootstrap-server", "kafka:9092", "consume", "--topic", "t", "--group", "g"]
    )
    assert args.command == "consume"
    assert args.from_beginning is False
    assert args.max_messages == 10
