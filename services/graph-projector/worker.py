from __future__ import annotations

import json
import os
import signal
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from confluent_kafka import Producer

from python_common.production_config import kafka_config, validate_production_config

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
INPUT_TOPIC = "graph.mutation-requested.v1"
COMPLETED_TOPIC = "graph.mutation-completed.v1"
DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"

NODE_LABELS = {
    "upsert_document": ("Document",),
    "upsert_article": ("Article",),
    "upsert_source": ("Source",),
    "upsert_evidence": ("Evidence",),
    "upsert_claim": ("Claim",),
}
ENTITY_LABELS = {
    "Company": ("Entity", "Company"),
    "Organization": ("Entity", "Organization"),
    "GovernmentAgency": ("Entity", "GovernmentAgency"),
    "Person": ("Entity", "Person"),
    "Location": ("Entity", "Location"),
}
RELATIONSHIP_TYPES = {
    "link_published": "PUBLISHED",
    "link_article_document": "DERIVED_FROM",
    "link_mentions": "MENTIONS",
    "link_evidence_entity": "EVIDENCE_FOR",
    "link_evidence_claim": "EVIDENCE_FOR",
    "link_article_claim": "MAKES_CLAIM",
    "link_partnered_with": "PARTNERED_WITH",
    "link_acquired": "ACQUIRED",
    "link_invested_in": "INVESTED_IN",
    "link_competes_with": "COMPETES_WITH",
    "link_regulates": "REGULATES",
    "link_affects": "AFFECTS",
    "link_related_to": "RELATED_TO",
}


class PermanentMutationError(ValueError):
    """A malformed or unsupported mutation that must not be retried forever."""


@dataclass(frozen=True)
class Statement:
    query: str
    parameters: dict[str, Any]


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PermanentMutationError(f"{key} must be a non-empty string")
    return value


def _properties(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("properties", {})
    if not isinstance(value, dict):
        raise PermanentMutationError("properties must be an object")
    return value


def _tenant_id(event: dict[str, Any]) -> str:
    value = event.get("tenant_id")
    if not isinstance(value, str) or not value.strip():
        raise PermanentMutationError("tenant_id must be a non-empty string")
    return value


def parse_event(raw_value: bytes | str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_value)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermanentMutationError("event value must be valid JSON") from error
    if not isinstance(decoded, dict):
        raise PermanentMutationError("event value must be a JSON object")
    return decoded


def build_statement(event: dict[str, Any]) -> Statement:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise PermanentMutationError("event payload must be an object")

    mutation_type = _required_string(payload, "mutation_type")
    stable_id = _required_string(payload, "stable_id")
    properties = _properties(payload)
    tenant_id = _tenant_id(event)

    labels = NODE_LABELS.get(mutation_type)
    if mutation_type == "upsert_entity":
        entity_type = _required_string(payload, "entity_type")
        labels = ENTITY_LABELS.get(entity_type)
        if labels is None:
            raise PermanentMutationError(f"unsupported entity_type: {entity_type}")

    if labels is not None:
        label_set = " ".join(f"SET n:{label}" for label in labels)
        return Statement(
            query=(
                "MERGE (n:GraphNode {tenant_id: $tenant_id, stable_id: $stable_id}) "
                f"{label_set} "
                "SET n += $properties "
                "RETURN n.stable_id AS stable_id"
            ),
            parameters={
                "stable_id": stable_id,
                "tenant_id": tenant_id,
                "properties": properties | {"tenant_id": tenant_id},
            },
        )

    relationship_type = RELATIONSHIP_TYPES.get(mutation_type)
    if relationship_type is None:
        raise PermanentMutationError(f"unsupported mutation_type: {mutation_type}")

    from_id = _required_string(payload, "from_id")
    to_id = _required_string(payload, "to_id")
    return Statement(
        query=(
            "MERGE (a:GraphNode {tenant_id: $tenant_id, stable_id: $from_id}) "
            "MERGE (b:GraphNode {tenant_id: $tenant_id, stable_id: $to_id}) "
            f"MERGE (a)-[r:{relationship_type} {{stable_id: $stable_id}}]->(b) "
            "SET r += $properties "
            "RETURN r.stable_id AS stable_id"
        ),
        parameters={
            "stable_id": stable_id,
            "from_id": from_id,
            "to_id": to_id,
            "tenant_id": tenant_id,
            "properties": properties | {"tenant_id": tenant_id},
        },
    )


def completion_event(source: dict[str, Any], stable_id: str) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": COMPLETED_TOPIC,
        "schema_version": 1,
        "tenant_id": source.get("tenant_id"),
        "occurred_at": source.get("occurred_at", now),
        "ingested_at": now,
        "correlation_id": source.get("correlation_id"),
        "causation_id": source.get("event_id"),
        "origin": "graph-projector",
        "processing_stage": "graph-write-completed",
        "idempotency_key": f"{COMPLETED_TOPIC}:{stable_id}",
        "payload": {"stable_id": stable_id, "status": "applied"},
    }


def dlq_event(source: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "failed_event": source,
        "error_type": type(error).__name__,
        "error": str(error)[:500],
        "failed_at": datetime.now(UTC).isoformat(),
        "origin": "graph-projector",
    }


def publish(producer: Producer, topic: str, key: str, value: dict[str, Any]) -> None:
    producer.produce(
        topic,
        key=key.encode("utf-8"),
        value=json.dumps(value, separators=(",", ":")).encode("utf-8"),
    )


def main() -> None:
    from confluent_kafka import Consumer, Producer
    from neo4j import GraphDatabase

    validate_production_config(["kafka", "neo4j"])
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    consumer = Consumer(
        kafka_config(
            **{
                "group.id": "signalchord-graph-projector-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "signalchord-dev")),
    )
    consumer.subscribe([INPUT_TOPIC])

    try:
        driver.verify_connectivity()
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())

            source: dict[str, Any] | None = None
            try:
                source = parse_event(message.value())
                statement = build_statement(source)
                with driver.session() as session:
                    session.execute_write(
                        lambda tx: tx.run(statement.query, **statement.parameters).consume()
                    )
                stable_id = statement.parameters["stable_id"]
                publish(producer, COMPLETED_TOPIC, stable_id, completion_event(source, stable_id))
            except PermanentMutationError as error:
                if source is None:
                    source = {"event_id": "invalid", "payload": {}}
                payload = source.get("payload", {})
                if not isinstance(payload, dict):
                    payload = {}
                key = payload.get("stable_id", source.get("event_id", "invalid"))
                publish(producer, DLQ_TOPIC, str(key), dlq_event(source, error))

            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()
        producer.flush(10)
        driver.close()


if __name__ == "__main__":
    main()
