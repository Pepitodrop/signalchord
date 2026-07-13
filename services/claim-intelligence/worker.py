from __future__ import annotations

import json
import os
import signal
import uuid
from datetime import UTC, datetime

from confluent_kafka import Consumer, Producer

from engine import cluster_claim

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")


def envelope(source: dict, event_type: str, key: str, payload: dict, stage: str) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "tenant_id": source["tenant_id"],
        "occurred_at": source.get("occurred_at", now),
        "ingested_at": now,
        "correlation_id": source["correlation_id"],
        "causation_id": source["event_id"],
        "origin": "claim-intelligence",
        "processing_stage": stage,
        "idempotency_key": f"{event_type}:{key}:claim-intelligence:1.0.0",
        "payload": payload,
    }


def publish(producer: Producer, topic: str, key: str, event: dict) -> None:
    producer.produce(topic, key=key.encode(), value=json.dumps(event, separators=(",", ":")).encode())


def graph_mutations(source: dict, payload: dict, cluster_id: str, normalized: str) -> list[tuple[str, dict]]:
    claim_id = payload["claim_id"]
    document_id = payload["document_id"]
    article_id = f"article:{document_id}"
    evidence = payload["evidence"]
    now = datetime.now(UTC).isoformat()
    common = {
        "tenant_id": source["tenant_id"],
        "observed_at": source.get("occurred_at"),
        "created_at": now,
        "updated_at": now,
    }
    return [
        (
            claim_id,
            {
                "mutation_type": "upsert_claim",
                "stable_id": claim_id,
                "properties": common
                | {
                    "proposition": payload["proposition"],
                    "normalized_proposition": normalized,
                    "cluster_id": cluster_id,
                    "confidence": payload["confidence"],
                    "status": "candidate",
                    "extraction_model": payload.get("extraction_model"),
                    "extraction_version": payload.get("extraction_version"),
                },
            },
        ),
        (
            evidence["evidence_id"],
            {
                "mutation_type": "upsert_evidence",
                "stable_id": evidence["evidence_id"],
                "properties": common
                | {
                    "document_id": document_id,
                    "start_offset": evidence["start_offset"],
                    "end_offset": evidence["end_offset"],
                    "span_hash": evidence["span_hash"],
                    "kind": "model_extraction",
                    "confidence": payload["confidence"],
                },
            },
        ),
        (
            f"article-claim:{article_id}:{claim_id}",
            {
                "mutation_type": "link_article_claim",
                "stable_id": f"article-claim:{article_id}:{claim_id}",
                "from_id": article_id,
                "to_id": claim_id,
                "properties": common | {"confidence": payload["confidence"]},
            },
        ),
        (
            f"evidence-claim:{evidence['evidence_id']}:{claim_id}",
            {
                "mutation_type": "link_evidence_claim",
                "stable_id": f"evidence-claim:{evidence['evidence_id']}:{claim_id}",
                "from_id": evidence["evidence_id"],
                "to_id": claim_id,
                "properties": common | {"confidence": payload["confidence"]},
            },
        ),
    ]


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
            "group.id": "signalchord-claim-intelligence-v1",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    producer = Producer({"bootstrap.servers": BROKERS, "enable.idempotence": True, "acks": "all"})
    consumer.subscribe(["claim.extracted.v1"])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            source = json.loads(message.value())
            payload = source["payload"]
            clustered = cluster_claim(payload["proposition"])
            clustered_payload = payload | {
                "cluster_id": clustered.cluster_id,
                "normalized_proposition": clustered.normalized_proposition,
                "stance": clustered.stance,
            }
            publish(
                producer,
                "claim.clustered.v1",
                clustered.cluster_id,
                envelope(source, "claim.clustered.v1", clustered.cluster_id, clustered_payload, "claim-clustering"),
            )
            for key, mutation in graph_mutations(source, payload, clustered.cluster_id, clustered.normalized_proposition):
                publish(
                    producer,
                    "graph.mutation-requested.v1",
                    key,
                    envelope(source, "graph.mutation-requested.v1", key, mutation, "graph-mutation-build"),
                )
            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
