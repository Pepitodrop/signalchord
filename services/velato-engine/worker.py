from __future__ import annotations
import importlib.util
import json
import os
import signal
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from confluent_kafka import Consumer, Producer

spec = importlib.util.spec_from_file_location("velato_engine", Path(__file__).with_name("engine.py"))
engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")

def main() -> None:
    running = True
    def stop(*_: object) -> None:
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer = Consumer({"bootstrap.servers": BROKERS, "group.id": "signalchord-velato-v1", "enable.auto.commit": False, "auto.offset.reset": "earliest"})
    producer = Producer({"bootstrap.servers": BROKERS, "enable.idempotence": True, "acks": "all"})
    consumer.subscribe(["alert.policy-evaluation-requested.v1"])
    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise RuntimeError(msg.error())
            source = json.loads(msg.value())
            result = engine.execute(engine.default_policy_ir(), source["payload"]["inputs"])
            now = datetime.now(UTC).isoformat()
            payload = {"alert_id": str(uuid.uuid4()), "policy_id": source["payload"]["policy_id"], "policy_version_id": source["payload"]["policy_version_id"], **result.model_dump(), "evidence_ids": source["payload"].get("evidence_ids", []), "graph_path_ids": []}
            event = {"event_id": str(uuid.uuid4()), "event_type": "alert.created.v1", "schema_version": 1, "tenant_id": source["tenant_id"], "occurred_at": now, "ingested_at": now, "correlation_id": source["correlation_id"], "causation_id": source["event_id"], "origin": "velato-engine", "processing_stage": "policy-evaluation", "idempotency_key": f"alert:{source['payload']['policy_version_id']}:{source['idempotency_key']}", "payload": payload}
            producer.produce("alert.created.v1", key=payload["alert_id"].encode(), value=json.dumps(event, separators=(",", ":")).encode())
            producer.flush(10)
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
