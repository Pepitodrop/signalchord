from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from confluent_kafka import Consumer, Producer

from python_common.production_config import kafka_config, validate_production_config

spec = importlib.util.spec_from_file_location(
    "velato_engine", Path(__file__).with_name("engine.py")
)
engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
DEFAULT_POLICY_PATH = Path(
    os.getenv(
        "DEFAULT_VELATO_POLICY_PATH",
        "/workspace/velato/programs/default-watchlist-novelty-v1.mid",
    )
)


def load_default_policy() -> tuple[list, str, str | None]:
    try:
        source = DEFAULT_POLICY_PATH.read_bytes()
        source_hash = hashlib.sha256(source).hexdigest()
        ir = engine.compile_notes(engine.parse_midi(source))
        return ir, "velato-midi", source_hash
    except (OSError, ValueError):
        return engine.default_policy_ir(), "fallback-rules", None


def main() -> None:
    validate_production_config(["kafka"])
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer = Consumer(
        kafka_config(
            **{
                "group.id": "signalchord-velato-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    policy_ir, execution_engine, policy_source_hash = load_default_policy()
    policy_ir_hash = engine.ir_sha256(policy_ir)
    policy_analysis = engine.analyze_ir(policy_ir).model_dump()
    consumer.subscribe(["alert.policy-evaluation-requested.v1"])
    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise RuntimeError(msg.error())
            source = json.loads(msg.value())
            result = engine.execute(policy_ir, source["payload"]["inputs"])
            now = datetime.now(UTC).isoformat()
            stable_alert_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{source['tenant_id']}:{source['payload']['policy_version_id']}:{source['idempotency_key']}",
                )
            )
            payload = {
                "alert_id": stable_alert_id,
                "policy_id": source["payload"]["policy_id"],
                "policy_version_id": source["payload"]["policy_version_id"],
                **result.model_dump(),
                "evidence_ids": source["payload"].get("evidence_ids", []),
                "graph_path_ids": source["payload"].get("graph_path_ids", []),
                "title": source["payload"].get(
                    "title", "SignalChord intelligence alert"
                ),
                "summary": source["payload"].get(
                    "summary", "A configured intelligence policy produced an alert."
                ),
                "execution_engine": execution_engine,
                "velato_dialect_version": engine.DIALECT_VERSION,
                "policy_source_sha256": policy_source_hash,
                "policy_ir_sha256": policy_ir_hash,
                "policy_analysis": policy_analysis,
            }
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "alert.created.v1",
                "schema_version": 1,
                "tenant_id": source["tenant_id"],
                "occurred_at": now,
                "ingested_at": now,
                "correlation_id": source["correlation_id"],
                "causation_id": source["event_id"],
                "origin": "velato-engine",
                "processing_stage": "policy-evaluation",
                "idempotency_key": (
                    f"alert:{source['payload']['policy_version_id']}:{source['idempotency_key']}"
                ),
                "payload": payload,
            }
            producer.produce(
                "alert.created.v1",
                key=payload["alert_id"].encode(),
                value=json.dumps(event, separators=(",", ":")).encode(),
            )
            producer.flush(10)
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
