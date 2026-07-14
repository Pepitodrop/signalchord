from __future__ import annotations

import json
import os
import signal
import uuid
from datetime import UTC, datetime

from confluent_kafka import Consumer, Producer

from python_common.production_config import kafka_config, validate_production_config
from resolver import DEFAULT_ALIASES, resolve_mention

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
ALIASES = DEFAULT_ALIASES
PREDICATE_MUTATIONS = {
    "PARTNERED_WITH": "link_partnered_with",
    "ACQUIRED": "link_acquired",
    "INVESTED_IN": "link_invested_in",
    "COMPETES_WITH": "link_competes_with",
    "REGULATES": "link_regulates",
    "AFFECTS": "link_affects",
    "RELATED_TO": "link_related_to",
}


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
        "origin": "entity-resolution",
        "processing_stage": stage,
        "idempotency_key": f"{event_type}:{key}:resolver:1.0.0",
        "payload": payload,
    }


def publish(producer: Producer, topic: str, key: str, event: dict) -> None:
    producer.produce(topic, key=key.encode(), value=json.dumps(event, separators=(",", ":")).encode())


def common_properties(source: dict) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "tenant_id": source["tenant_id"],
        "observed_at": source.get("occurred_at"),
        "created_at": now,
        "updated_at": now,
    }


def graph_events(source: dict, resolution: dict) -> list[tuple[str, dict]]:
    document_id = resolution["document_id"]
    article_id = f"article:{document_id}"
    entity_id = resolution["entity_id"]
    evidence = resolution["evidence"]
    common = common_properties(source)
    return [
        (
            entity_id,
            {
                "mutation_type": "upsert_entity",
                "stable_id": entity_id,
                "entity_type": resolution["entity_type"],
                "properties": common
                | {
                    "display_name": resolution["display_name"],
                    "normalized_name": resolution["display_name"].casefold(),
                    "confidence": resolution["confidence"],
                    "status": resolution["status"],
                    "extraction_model": resolution.get("extraction_model"),
                    "extraction_version": resolution.get("extraction_version"),
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
                    "confidence": resolution["confidence"],
                },
            },
        ),
        (
            f"mentions:{article_id}:{entity_id}:{resolution['mention_id']}",
            {
                "mutation_type": "link_mentions",
                "stable_id": f"mentions:{resolution['mention_id']}",
                "from_id": article_id,
                "to_id": entity_id,
                "properties": common
                | {
                    "mention_id": resolution["mention_id"],
                    "confidence": resolution["confidence"],
                    "status": resolution["status"],
                    "evidence_id": evidence["evidence_id"],
                },
            },
        ),
        (
            f"evidence-entity:{evidence['evidence_id']}:{entity_id}",
            {
                "mutation_type": "link_evidence_entity",
                "stable_id": f"evidence-entity:{evidence['evidence_id']}:{entity_id}",
                "from_id": evidence["evidence_id"],
                "to_id": entity_id,
                "properties": common | {"confidence": resolution["confidence"]},
            },
        ),
    ]


def relation_graph_events(source: dict, payload: dict) -> list[tuple[str, dict]]:
    subject_payload = payload["subject"] | {
        "document_id": payload["document_id"],
        "extraction_model": payload.get("extraction_model"),
        "extraction_version": payload.get("extraction_version"),
    }
    object_payload = payload["object"] | {
        "document_id": payload["document_id"],
        "extraction_model": payload.get("extraction_model"),
        "extraction_version": payload.get("extraction_version"),
    }
    subject = resolve_mention(subject_payload, ALIASES)
    object_ = resolve_mention(object_payload, ALIASES)
    common = common_properties(source)
    relationship_id = payload["relationship_id"]
    mutation_type = PREDICATE_MUTATIONS.get(payload["predicate"], "link_related_to")
    events = graph_events(source, subject) + graph_events(source, object_)
    events.append(
        (
            relationship_id,
            {
                "mutation_type": mutation_type,
                "stable_id": relationship_id,
                "from_id": subject["entity_id"],
                "to_id": object_["entity_id"],
                "properties": common
                | {
                    "confidence": payload["confidence"],
                    "status": "candidate",
                    "evidence_id": payload["evidence"]["evidence_id"],
                    "extraction_model": payload.get("extraction_model"),
                    "extraction_version": payload.get("extraction_version"),
                    "valid_from": source.get("occurred_at"),
                },
            },
        )
    )
    return events


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
                "group.id": "signalchord-entity-resolution-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    consumer.subscribe(["entity.mention-extracted.v1", "relationship.extracted.v1"])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            source = json.loads(message.value())
            if source["event_type"] == "entity.mention-extracted.v1":
                resolution = resolve_mention(source["payload"], ALIASES)
                publish(
                    producer,
                    "entity.resolved.v1",
                    resolution["entity_id"],
                    envelope(source, "entity.resolved.v1", resolution["entity_id"], resolution, "entity-resolution"),
                )
                mutations = graph_events(source, resolution)
            else:
                mutations = relation_graph_events(source, source["payload"])
            for key, mutation in mutations:
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
