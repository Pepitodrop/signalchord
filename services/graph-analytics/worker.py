from __future__ import annotations

import json
import os
import signal
import uuid
from datetime import UTC, datetime

from confluent_kafka import Consumer, Producer
from neo4j import GraphDatabase

from app import AnalysisRequest, analyze

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "signalchord-dev")


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
            "group.id": "signalchord-graph-analytics-v1",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    producer = Producer({"bootstrap.servers": BROKERS, "enable.idempotence": True, "acks": "all"})
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    consumer.subscribe(["graph.analytics-requested.v1"])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            source = json.loads(message.value())
            request = AnalysisRequest(
                tenant_id=source["tenant_id"],
                entity_id=source["payload"]["entity_id"],
                lookback_days=source["payload"].get("lookback_days", 7),
            )
            result = analyze(driver, request)
            now = datetime.now(UTC).isoformat()
            payload = result.model_dump(mode="json") | {
                "signal_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{request.tenant_id}:{request.entity_id}:{source['event_id']}")),
                "algorithm_version": "1.0.0",
            }
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "intelligence.signal-created.v1",
                "schema_version": 1,
                "tenant_id": source["tenant_id"],
                "occurred_at": source.get("occurred_at", now),
                "ingested_at": now,
                "correlation_id": source["correlation_id"],
                "causation_id": source["event_id"],
                "origin": "graph-analytics",
                "processing_stage": "graph-analytics",
                "idempotency_key": f"graph-analytics:{request.entity_id}:{source['event_id']}:1.0.0",
                "payload": payload,
            }
            producer.produce(
                "intelligence.signal-created.v1",
                key=request.entity_id.encode(),
                value=json.dumps(event, separators=(",", ":")).encode(),
            )
            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
    finally:
        driver.close()
        consumer.close()


if __name__ == "__main__":
    main()
