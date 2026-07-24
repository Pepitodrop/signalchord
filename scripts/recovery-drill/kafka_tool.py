#!/usr/bin/env python3
"""Kafka helper for the recovery-drill CI job: produce / consume / offsets.

This is a thin CLI over confluent_kafka, used only to inject test messages
and read back what happened (DLQ contents, consumer-group offsets) during
the drill. It does not implement any replay or classification logic itself
-- scripts/single-server/replay-kafka.sh remains the only thing that resets
offsets, and services/python_common/poison_message.py /
services/internal/kafkautil remain the only thing that classifies and
publishes to a DLQ. This tool only observes.

Intended to run from inside the cluster (a Kafka broker's advertised
listener is only reachable there), which is why every subcommand takes an
explicit --bootstrap-server rather than assuming a default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any


def parse_headers(pairs: list[str] | None) -> list[tuple[str, bytes]]:
    """Parse ["key=value", ...] CLI header pairs into confluent_kafka's
    list-of-(str, bytes) header format."""
    headers: list[tuple[str, bytes]] = []
    for pair in pairs or []:
        key, separator, value = pair.partition("=")
        if not separator:
            raise ValueError(f"malformed header {pair!r}; expected key=value")
        headers.append((key, value.encode("utf-8")))
    return headers


def decode_optional(value: bytes | None) -> str | None:
    if value is None:
        return None
    return value.decode("utf-8", errors="replace")


def format_message(message: Any) -> dict[str, Any]:
    """Convert a confluent_kafka Message into a JSON-serializable dict."""
    headers = {}
    for header_key, header_value in message.headers() or []:
        headers[header_key] = decode_optional(header_value)
    return {
        "topic": message.topic(),
        "partition": message.partition(),
        "offset": message.offset(),
        "key": decode_optional(message.key()),
        "value": decode_optional(message.value()),
        "headers": headers,
    }


def format_offsets(committed: dict[str, int], watermarks: dict[str, tuple[int, int]]) -> dict[str, Any]:
    """Merge committed-offset and (low, high) watermark data into one
    per-partition report, keyed by "topic-partition"."""
    result: dict[str, Any] = {}
    for key, high_low in watermarks.items():
        low, high = high_low
        result[key] = {
            "committed_offset": committed.get(key),
            "log_start_offset": low,
            "log_end_offset": high,
        }
    return result


def cmd_produce(args: argparse.Namespace) -> int:
    from confluent_kafka import Producer

    if args.value is not None:
        value = args.value.encode("utf-8")
    elif args.value_file is not None:
        with open(args.value_file, "rb") as handle:
            value = handle.read()
    else:
        value = None

    delivery_error: Any = None
    delivered: dict[str, Any] = {}

    def on_delivery(err: Any, message: Any) -> None:
        nonlocal delivery_error
        if err is not None:
            delivery_error = err
            return
        delivered["partition"] = message.partition()
        delivered["offset"] = message.offset()

    producer = Producer({"bootstrap.servers": args.bootstrap_server})
    producer.produce(
        args.topic,
        key=args.key.encode("utf-8") if args.key is not None else None,
        value=value,
        headers=parse_headers(args.header),
        on_delivery=on_delivery,
    )
    pending = producer.flush(args.timeout_seconds)
    if pending > 0:
        print(f"timed out waiting for delivery confirmation ({pending} pending)", file=sys.stderr)
        return 1
    if delivery_error is not None:
        print(f"delivery failed: {delivery_error}", file=sys.stderr)
        return 1
    print(json.dumps({"topic": args.topic, "key": args.key, **delivered}))
    return 0


def cmd_consume(args: argparse.Namespace) -> int:
    from confluent_kafka import Consumer

    config = {
        "bootstrap.servers": args.bootstrap_server,
        "group.id": args.group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest" if args.from_beginning else "latest",
    }
    consumer = Consumer(config)
    consumer.subscribe([args.topic])
    seen: list[dict[str, Any]] = []
    deadline = time.time() + args.timeout_seconds
    try:
        while time.time() < deadline and len(seen) < args.max_messages:
            message = consumer.poll(1.0)
            if message is None or message.error():
                continue
            seen.append(format_message(message))
    finally:
        consumer.close()
    for item in seen:
        print(json.dumps(item))
    return 0


def cmd_offsets(args: argparse.Namespace) -> int:
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.admin import AdminClient, ConsumerGroupTopicPartitions

    admin = AdminClient({"bootstrap.servers": args.bootstrap_server})
    futures = admin.list_consumer_group_offsets([ConsumerGroupTopicPartitions(args.group)])
    result = futures[args.group].result(timeout=args.timeout_seconds)
    committed = {
        f"{tp.topic}-{tp.partition}": tp.offset
        for tp in result.topic_partitions
        if tp.topic == args.topic and tp.offset >= 0
    }

    probe = Consumer({"bootstrap.servers": args.bootstrap_server, "group.id": f"{args.group}-watermark-probe"})
    try:
        partition_metadata = probe.list_topics(args.topic, timeout=args.timeout_seconds).topics[args.topic].partitions
        watermarks = {}
        for partition_id in partition_metadata:
            low, high = probe.get_watermark_offsets(
                TopicPartition(args.topic, partition_id), timeout=args.timeout_seconds, cached=False
            )
            watermarks[f"{args.topic}-{partition_id}"] = (low, high)
    finally:
        probe.close()

    print(json.dumps(format_offsets(committed, watermarks)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-server", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Publish one message")
    produce.add_argument("--topic", required=True)
    produce.add_argument("--key")
    produce.add_argument("--value")
    produce.add_argument("--value-file")
    produce.add_argument("--header", action="append")
    produce.add_argument("--timeout-seconds", type=float, default=10.0)
    produce.set_defaults(func=cmd_produce)

    consume = subparsers.add_parser("consume", help="Read messages, one JSON object per line")
    consume.add_argument("--topic", required=True)
    consume.add_argument("--group", required=True)
    consume.add_argument("--from-beginning", action="store_true")
    consume.add_argument("--max-messages", type=int, default=10)
    consume.add_argument("--timeout-seconds", type=float, default=20.0)
    consume.set_defaults(func=cmd_consume)

    offsets = subparsers.add_parser("offsets", help="Report committed offsets and watermarks for a group/topic")
    offsets.add_argument("--topic", required=True)
    offsets.add_argument("--group", required=True)
    offsets.add_argument("--timeout-seconds", type=float, default=10.0)
    offsets.set_defaults(func=cmd_offsets)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
