from __future__ import annotations

import json
import os
import signal
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from confluent_kafka import Consumer
from opensearchpy import OpenSearch

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
MAX_TEXT_BYTES = 5_000_000


def storage_client():
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


def search_client() -> OpenSearch:
    parsed = urlparse(os.getenv("OPENSEARCH_URL", "http://localhost:9200"))
    return OpenSearch(
        hosts=[{"host": parsed.hostname or "localhost", "port": parsed.port or 9200, "scheme": parsed.scheme}],
        use_ssl=parsed.scheme == "https",
        verify_certs=os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true",
    )


def ensure_indexes(client: OpenSearch) -> None:
    mappings = {
        "signalchord-articles": {
            "properties": {
                "tenant_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "canonical_url": {"type": "keyword"},
                "content": {"type": "text"},
                "published_at": {"type": "date"},
                "observed_at": {"type": "date"},
            }
        },
        "signalchord-entities": {
            "properties": {
                "tenant_id": {"type": "keyword"},
                "stable_id": {"type": "keyword"},
                "display_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "entity_type": {"type": "keyword"},
                "confidence": {"type": "float"},
                "status": {"type": "keyword"},
            }
        },
        "signalchord-claims": {
            "properties": {
                "tenant_id": {"type": "keyword"},
                "claim_id": {"type": "keyword"},
                "cluster_id": {"type": "keyword"},
                "proposition": {"type": "text"},
                "stance": {"type": "keyword"},
                "confidence": {"type": "float"},
            }
        },
    }
    for index, mapping in mappings.items():
        if not client.indices.exists(index=index):
            client.indices.create(index=index, body={"mappings": mapping})


def load_text(storage, uri: str) -> str:
    parsed = urlparse(uri)
    response = storage.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
    body = response["Body"].read(MAX_TEXT_BYTES + 1)
    if len(body) > MAX_TEXT_BYTES:
        raise ValueError("document exceeds search projection limit")
    return body.decode("utf-8")


def project(client: OpenSearch, storage, event: dict) -> None:
    payload = event["payload"]
    event_type = event["event_type"]
    tenant_id = event["tenant_id"]
    if event_type == "document.normalized.v1":
        content = load_text(storage, payload["clean_text_object_uri"])
        client.index(
            index="signalchord-articles",
            id=f"{tenant_id}:{payload['document_id']}",
            body={
                "tenant_id": tenant_id,
                "document_id": payload["document_id"],
                "title": payload.get("title"),
                "canonical_url": payload.get("canonical_url"),
                "content": content,
                "published_at": payload.get("published_at"),
                "observed_at": event.get("occurred_at"),
            },
            refresh=False,
        )
    elif event_type == "entity.resolved.v1":
        client.index(
            index="signalchord-entities",
            id=f"{tenant_id}:{payload['entity_id']}",
            body={
                "tenant_id": tenant_id,
                "stable_id": payload["entity_id"],
                "display_name": payload["display_name"],
                "entity_type": payload["entity_type"],
                "confidence": payload["confidence"],
                "status": payload["status"],
            },
            refresh=False,
        )
    elif event_type == "claim.clustered.v1":
        client.index(
            index="signalchord-claims",
            id=f"{tenant_id}:{payload['claim_id']}",
            body={
                "tenant_id": tenant_id,
                "claim_id": payload["claim_id"],
                "cluster_id": payload["cluster_id"],
                "proposition": payload["proposition"],
                "stance": payload["stance"],
                "confidence": payload["confidence"],
            },
            refresh=False,
        )


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
            "group.id": "signalchord-search-projector-v1",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    client = search_client()
    storage = storage_client()
    ensure_indexes(client)
    consumer.subscribe(["document.normalized.v1", "entity.resolved.v1", "claim.clustered.v1"])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(message.error())
            project(client, storage, json.loads(message.value()))
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
