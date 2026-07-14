from __future__ import annotations

import json
import os
import signal
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from confluent_kafka import Consumer, Producer

from app import Document, extract
from python_common.production_config import kafka_config, validate_production_config

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
INPUT_TOPIC = "document.nlp-requested.v1"
MAX_TEXT_BYTES = 5_000_000


def envelope(
    event_type: str,
    tenant_id: str,
    correlation_id: str,
    causation_id: str,
    key: str,
    payload: dict,
    stage: str,
    occurred_at: str | None = None,
) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "tenant_id": tenant_id,
        "occurred_at": occurred_at or now,
        "ingested_at": now,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "origin": "nlp-pipeline",
        "processing_stage": stage,
        "idempotency_key": f"{event_type}:{key}:signalchord-rules:1.0.0",
        "payload": payload,
    }


def publish(producer: Producer, topic: str, key: str, value: dict) -> None:
    producer.produce(
        topic,
        key=key.encode(),
        value=json.dumps(value, separators=(",", ":")).encode(),
    )


def object_client():
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    scheme = "https" if os.getenv("MINIO_SECURE", "false").lower() == "true" else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{endpoint}",
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "signalchord"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "signalchord-dev-secret"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def load_text(payload: dict, client) -> str:
    inline = payload.get("text")
    if isinstance(inline, str):
        if len(inline.encode()) > MAX_TEXT_BYTES:
            raise ValueError("inline text exceeds limit")
        return inline
    uri = payload.get("clean_text_object_uri")
    if not isinstance(uri, str) or not uri.startswith("s3://"):
        raise ValueError("missing clean text object URI")
    parsed = urlparse(uri)
    response = client.get_object(
        Bucket=parsed.netloc,
        Key=parsed.path.lstrip("/"),
        Range=f"bytes=0-{MAX_TEXT_BYTES}",
    )
    body = response["Body"].read(MAX_TEXT_BYTES + 1)
    if len(body) > MAX_TEXT_BYTES:
        raise ValueError("clean text exceeds limit")
    return body.decode("utf-8", errors="strict")


def graph_base_mutations(source: dict, payload: dict, result) -> list[tuple[str, dict]]:
    document_id = payload["document_id"]
    article_id = f"article:{document_id}"
    now = datetime.now(UTC).isoformat()
    common = {
        "tenant_id": source["tenant_id"],
        "observed_at": source.get("occurred_at"),
        "created_at": now,
        "updated_at": now,
        "extraction_model": result.extraction_model,
        "extraction_version": result.extraction_version,
    }
    return [
        (
            document_id,
            {
                "mutation_type": "upsert_document",
                "stable_id": document_id,
                "properties": common
                | {
                    "status": "model_verified",
                    "confidence": 1.0,
                    "canonical_url": payload.get("canonical_url"),
                    "title": payload.get("title"),
                    "clean_text_object_uri": payload.get("clean_text_object_uri"),
                },
            },
        ),
        (
            article_id,
            {
                "mutation_type": "upsert_article",
                "stable_id": article_id,
                "properties": common
                | {
                    "document_id": document_id,
                    "title": payload.get("title"),
                    "canonical_url": payload.get("canonical_url"),
                    "published_at": payload.get("published_at"),
                    "language": result.language,
                    "topics": result.topics,
                    "embedding": result.embedding,
                    "status": "model_verified",
                },
            },
        ),
        (
            payload.get("source_id", "source:unknown"),
            {
                "mutation_type": "upsert_source",
                "stable_id": payload.get("source_id", "source:unknown"),
                "properties": common | {"status": "active"},
            },
        ),
        (
            f"published:{article_id}:{payload.get('source_id', 'source:unknown')}",
            {
                "mutation_type": "link_published",
                "stable_id": f"published:{article_id}:{payload.get('source_id', 'source:unknown')}",
                "from_id": article_id,
                "to_id": payload.get("source_id", "source:unknown"),
                "properties": common,
            },
        ),
        (
            f"article-document:{article_id}:{document_id}",
            {
                "mutation_type": "link_article_document",
                "stable_id": f"article-document:{article_id}:{document_id}",
                "from_id": article_id,
                "to_id": document_id,
                "properties": common,
            },
        ),
    ]


def main() -> None:
    validate_production_config(["kafka", "minio"])
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer = Consumer(
        kafka_config(
            **{
                "group.id": "signalchord-nlp-v1",
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
    )
    producer = Producer(kafka_config(**{"enable.idempotence": True, "acks": "all"}))
    storage = object_client()
    consumer.subscribe([INPUT_TOPIC])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            source = json.loads(message.value())
            payload = source["payload"]
            text = load_text(payload, storage)
            result = extract(
                Document(
                    document_id=payload["document_id"],
                    text=text,
                    language_hint=payload.get("language_hint"),
                )
            )
            tenant_id = source["tenant_id"]
            correlation_id = source["correlation_id"]
            causation_id = source["event_id"]
            occurred_at = source.get("occurred_at")

            for key, mutation in graph_base_mutations(source, payload, result):
                publish(
                    producer,
                    "graph.mutation-requested.v1",
                    key,
                    envelope(
                        "graph.mutation-requested.v1",
                        tenant_id,
                        correlation_id,
                        causation_id,
                        key,
                        mutation,
                        "graph-mutation-build",
                        occurred_at,
                    ),
                )

            for mention in result.mentions:
                data = mention.model_dump(mode="json") | {
                    "document_id": payload["document_id"],
                    "extraction_model": result.extraction_model,
                    "extraction_version": result.extraction_version,
                }
                publish(
                    producer,
                    "entity.mention-extracted.v1",
                    payload["document_id"],
                    envelope(
                        "entity.mention-extracted.v1",
                        tenant_id,
                        correlation_id,
                        causation_id,
                        mention.mention_id,
                        data,
                        "entity-extraction",
                        occurred_at,
                    ),
                )
            for claim in result.claims:
                data = claim.model_dump(mode="json") | {
                    "document_id": payload["document_id"],
                    "extraction_model": result.extraction_model,
                    "extraction_version": result.extraction_version,
                }
                publish(
                    producer,
                    "claim.extracted.v1",
                    claim.claim_id,
                    envelope(
                        "claim.extracted.v1",
                        tenant_id,
                        correlation_id,
                        causation_id,
                        claim.claim_id,
                        data,
                        "claim-extraction",
                        occurred_at,
                    ),
                )
            mention_by_id = {mention.mention_id: mention for mention in result.mentions}
            for relation in result.relations:
                data = relation.model_dump(mode="json") | {
                    "document_id": payload["document_id"],
                    "subject": mention_by_id[relation.subject_mention_id].model_dump(mode="json"),
                    "object": mention_by_id[relation.object_mention_id].model_dump(mode="json"),
                    "extraction_model": result.extraction_model,
                    "extraction_version": result.extraction_version,
                }
                publish(
                    producer,
                    "relationship.extracted.v1",
                    relation.relationship_id,
                    envelope(
                        "relationship.extracted.v1",
                        tenant_id,
                        correlation_id,
                        causation_id,
                        relation.relationship_id,
                        data,
                        "relation-extraction",
                        occurred_at,
                    ),
                )

            graph_path_ids = [relation.relationship_id for relation in result.relations]
            policy_inputs = {
                "policy_id": "default-watchlist-novelty",
                "policy_version_id": "v1",
                "inputs": {
                    "source_trust": 0.75,
                    "corroboration_count": 1,
                    "contradiction_count": 0,
                    "novelty": 0.8,
                    "entity_relevance": min(1.0, 0.4 + len(result.mentions) * 0.15),
                    "graph_centrality": 0.4,
                    "geographic_relevance": 0.8 if any(m.entity_type == "Location" for m in result.mentions) else 0.2,
                    "watchlist_match": 1.0 if any("Acme" in m.text for m in result.mentions) else 0.0,
                    "recency": 1.0,
                    "source_diversity": 0.4,
                },
                "evidence_ids": [m.evidence.evidence_id for m in result.mentions]
                + [c.evidence.evidence_id for c in result.claims]
                + [r.evidence.evidence_id for r in result.relations],
                "graph_path_ids": graph_path_ids,
                "title": payload.get("title") or "New intelligence signal",
                "summary": f"Extracted {len(result.mentions)} entities, {len(result.claims)} claims and {len(result.relations)} relationships.",
            }
            publish(
                producer,
                "alert.policy-evaluation-requested.v1",
                payload["document_id"],
                envelope(
                    "alert.policy-evaluation-requested.v1",
                    tenant_id,
                    correlation_id,
                    causation_id,
                    payload["document_id"],
                    policy_inputs,
                    "policy-request",
                    occurred_at,
                ),
            )
            completed = {
                "document_id": payload["document_id"],
                "mentions": len(result.mentions),
                "claims": len(result.claims),
                "relations": len(result.relations),
                "topics": result.topics,
                "extraction_model": result.extraction_model,
                "extraction_version": result.extraction_version,
            }
            publish(
                producer,
                "document.nlp-completed.v1",
                payload["document_id"],
                envelope(
                    "document.nlp-completed.v1",
                    tenant_id,
                    correlation_id,
                    causation_id,
                    payload["document_id"],
                    completed,
                    "nlp-completed",
                    occurred_at,
                ),
            )
            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
