from __future__ import annotations

import json
import os
import signal
from typing import Any

import httpx
from confluent_kafka import Consumer, Producer

from python_common.poison_message import handle_message
from python_common.production_config import kafka_config, validate_production_config

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://control-plane:3000")
INTERNAL_TOKEN = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal")
EXPO_PUSH_URL = os.getenv("EXPO_PUSH_URL", "https://exp.host/--/api/v2/push/send")
INPUT_TOPIC = "notification.requested.v1"
DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"


class ExpoDeviceNotRegisteredError(ValueError):
    """The Expo push token is no longer registered to any device.

    Permanent: Expo will never successfully deliver to this token again, so
    retrying is pointless -- unlike rate limits, timeouts, 5xx responses or
    any other/unrecognized provider error, which stay transient (RuntimeError)
    since they may well succeed on a later retry.
    """


def expo_message(payload: dict[str, Any], token: str) -> dict[str, Any]:
    return {
        "to": token,
        "title": payload["title"],
        "body": payload.get("summary") or "A SignalChord alert requires your attention.",
        "priority": "high" if int(payload.get("severity_code", 0)) >= 2 else "default",
        "channelId": "alerts",
        "data": {
            "alert_id": payload["alert_id"],
            "stable_alert_id": payload.get("stable_alert_id"),
            "deep_link": f"signalchord://alert/{payload['alert_id']}",
        },
    }


def update_delivery(client: httpx.Client, delivery_id: str, status: str, **fields: Any) -> None:
    response = client.patch(
        f"{CONTROL_PLANE_URL}/internal/v1/notification_targets/{delivery_id}",
        headers={"X-SignalChord-Internal-Token": INTERNAL_TOKEN},
        json={"status": status, **fields},
    )
    response.raise_for_status()


def deliver(client: httpx.Client, event: dict[str, Any]) -> None:
    payload = event["payload"]
    response = client.post(
        f"{CONTROL_PLANE_URL}/internal/v1/notification_targets",
        headers={"X-SignalChord-Internal-Token": INTERNAL_TOKEN},
        json={
            "tenant_id": event["tenant_id"],
            "event_id": event["event_id"],
            "alert_id": payload["alert_id"],
        },
    )
    response.raise_for_status()
    for target in response.json().get("targets", []):
        delivery_id = target["delivery_id"]
        try:
            if target["platform"] not in {"expo", "ios", "android"}:
                raise ValueError(f"unsupported notification platform {target['platform']}")
            provider = client.post(EXPO_PUSH_URL, json=expo_message(payload, target["token"]))
            provider.raise_for_status()
            data = provider.json().get("data", {})
            provider_id = data.get("id") if isinstance(data, dict) else None
            provider_error = data.get("message") if isinstance(data, dict) else None
            if provider_error:
                details = data.get("details") if isinstance(data, dict) else None
                error_code = details.get("error") if isinstance(details, dict) else None
                if error_code == "DeviceNotRegistered":
                    raise ExpoDeviceNotRegisteredError(provider_error)
                # Every other Expo/provider error (rate limits, timeouts, 5xx,
                # unrecognized error codes) stays transient by design: RuntimeError
                # is not a ValueError, so the shared poison-message helper leaves
                # it uncaught and the message is retried rather than dropped.
                raise RuntimeError(provider_error)
            update_delivery(client, delivery_id, "delivered", provider_message_id=provider_id)
        except Exception as error:
            update_delivery(client, delivery_id, "failed", last_error=str(error)[:2_000])
            raise


def handle_one_message(
    message, consumer: Consumer, producer: Producer, client: httpx.Client
) -> None:
    def process() -> None:
        deliver(client, json.loads(message.value()))

    handle_message(
        consumer=consumer,
        message=message,
        producer=producer,
        dlq_topic=DLQ_TOPIC,
        process=process,
        origin="notification-worker",
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
                "group.id": "signalchord-notification-worker-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    client = httpx.Client(timeout=15)
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
