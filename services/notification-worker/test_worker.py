import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("notification_worker", Path(__file__).with_name("worker.py"))
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
