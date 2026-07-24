import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "notification_worker", Path(__file__).with_name("worker.py")
)
worker = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = worker
spec.loader.exec_module(worker)


def test_expo_message_contains_only_minimized_alert_fields() -> None:
    message = worker.expo_message(
        {
            "alert_id": "alert-1",
            "stable_alert_id": "stable-1",
            "title": "Relationship change",
            "summary": "A watched company has a new relationship.",
            "severity_code": 2,
        },
        "ExponentPushToken[test]",
    )
    assert message["to"] == "ExponentPushToken[test]"
    assert message["data"]["deep_link"] == "signalchord://alert/alert-1"
    assert "evidence" not in message


def _client_with_expo_response(expo_response: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/internal/v1/notification_targets":
            return httpx.Response(
                200,
                json={
                    "targets": [{"delivery_id": "delivery-1", "platform": "expo", "token": "tok-1"}]
                },
            )
        if str(request.url) == worker.EXPO_PUSH_URL:
            return httpx.Response(200, json=expo_response)
        if request.method == "PATCH":
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def _event() -> dict:
    return {
        "tenant_id": "tenant-1",
        "event_id": "e-1",
        "payload": {"alert_id": "alert-1", "title": "Alert"},
    }


def test_expo_device_not_registered_raises_permanent_error() -> None:
    client = _client_with_expo_response(
        {
            "data": {
                "status": "error",
                "message": "The Expo push token is not a registered push notification recipient",
                "details": {"error": "DeviceNotRegistered"},
            }
        }
    )

    with pytest.raises(worker.ExpoDeviceNotRegisteredError):
        worker.deliver(client, _event())


def test_expo_device_not_registered_is_a_value_error_subclass() -> None:
    assert issubclass(worker.ExpoDeviceNotRegisteredError, ValueError)


@pytest.mark.parametrize(
    "expo_response",
    [
        {
            "data": {
                "status": "error",
                "message": "Rate limit exceeded",
                "details": {"error": "MessageRateExceeded"},
            }
        },
        {
            "data": {
                "status": "error",
                "message": "Some unrecognized failure",
                "details": {"error": "SomethingNew"},
            }
        },
        {"data": {"status": "error", "message": "Some failure with no details"}},
    ],
)
def test_unknown_or_non_device_expo_errors_raise_transient_error(expo_response: dict) -> None:
    client = _client_with_expo_response(expo_response)

    with pytest.raises(RuntimeError) as exc_info:
        worker.deliver(client, _event())

    assert not isinstance(exc_info.value, ValueError)


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


def test_handle_one_message_routes_device_not_registered_to_dlq_and_commits() -> None:
    client = _client_with_expo_response(
        {
            "data": {
                "status": "error",
                "message": "not registered",
                "details": {"error": "DeviceNotRegistered"},
            }
        }
    )
    message = FakeMessage(json.dumps(_event()).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer, client)

    assert len(producer.produced) == 1
    assert producer.produced[0]["topic"] == worker.DLQ_TOPIC
    assert consumer.committed == [message]


def test_handle_one_message_does_not_commit_on_transient_provider_error() -> None:
    client = _client_with_expo_response(
        {
            "data": {
                "status": "error",
                "message": "Internal server error",
                "details": {"error": "unknown"},
            }
        }
    )
    message = FakeMessage(json.dumps(_event()).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    with pytest.raises(RuntimeError):
        worker.handle_one_message(message, consumer, producer, client)

    assert producer.produced == []
    assert consumer.committed == []


def test_handle_one_message_commits_after_successful_delivery() -> None:
    client = _client_with_expo_response({"data": {"status": "ok", "id": "receipt-1"}})
    message = FakeMessage(json.dumps(_event()).encode())
    producer = FakeProducer()
    consumer = FakeConsumer()

    worker.handle_one_message(message, consumer, producer, client)

    assert producer.produced == []
    assert consumer.committed == [message]
