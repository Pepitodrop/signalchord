from __future__ import annotations

import json
import os
import signal

import httpx
from confluent_kafka import Consumer

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://control-plane:3000")
INTERNAL_TOKEN = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal")


def project(client: httpx.Client, event: dict) -> None:
    response = client.post(
        f"{CONTROL_PLANE_URL}/internal/v1/alerts",
        headers={"X-SignalChord-Internal-Token": INTERNAL_TOKEN},
        json=event,
    )
    response.raise_for_status()


def main() -> None:
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer = Consumer(
        {
            "bootstrap.servers": BROKERS,
            "group.id": "signalchord-alert-projector-v1",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    client = httpx.Client(timeout=10)
    consumer.subscribe(["alert.created.v1"])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            project(client, json.loads(message.value()))
            consumer.commit(message=message, asynchronous=False)
    finally:
        client.close()
        consumer.close()


if __name__ == "__main__":
    main()
