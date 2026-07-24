from __future__ import annotations

import json
import os
import signal

import httpx
from confluent_kafka import Consumer, Producer

from python_common.poison_message import handle_message
from python_common.production_config import kafka_config, validate_production_config

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://control-plane:3000")
INTERNAL_TOKEN = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal")
INPUT_TOPIC = "alert.created.v1"
DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"


def project(client: httpx.Client, event: dict) -> None:
    response = client.post(
        f"{CONTROL_PLANE_URL}/internal/v1/alerts",
        headers={"X-SignalChord-Internal-Token": INTERNAL_TOKEN},
        json=event,
    )
    response.raise_for_status()


def handle_one_message(
    message, consumer: Consumer, producer: Producer, client: httpx.Client
) -> None:
    def process() -> None:
        project(client, json.loads(message.value()))

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic=DLQ_TOPIC,
        process=process,
        origin="alert-projector",
    )


def main() -> None:
    validate_production_config(["kafka", "control_plane", "internal_token"])
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer = Consumer(
        kafka_config(
            **{
                "group.id": "signalchord-alert-projector-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    client = httpx.Client(timeout=10)
    consumer.subscribe([INPUT_TOPIC])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            handle_one_message(message, consumer, producer, client)
    finally:
        client.close()
        consumer.close()
        producer.flush(10)


if __name__ == "__main__":
    main()
