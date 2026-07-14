from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("worker.py")
SPEC = importlib.util.spec_from_file_location("signalchord_search_projector_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)


class FakeSearchClient:
    def __init__(self):
        self.indexed: list[dict] = []
        self.deleted: list[dict] = []

    def index(self, **kwargs):
        self.indexed.append(kwargs)

    def delete_by_query(self, **kwargs):
        self.deleted.append(kwargs)


class FakeStorage:
    def get_object(self, Bucket: str, Key: str):
        assert Bucket == "raw-documents"
        assert Key == "tenant-a/doc.txt"
        return {"Body": BytesIO(b"tenant-a article body")}


def test_document_projection_uses_tenant_prefixed_id_and_body_filter_field() -> None:
    client = FakeSearchClient()
    event = {
        "event_type": "document.normalized.v1",
        "tenant_id": "tenant-a",
        "occurred_at": "2026-01-01T00:00:00Z",
            "payload": {
                "document_id": "doc-1",
                "source_id": "source-1",
                "clean_text_object_uri": "s3://raw-documents/tenant-a/doc.txt",
            "title": "Tenant article",
            "canonical_url": "https://tenant-a.example/article",
        },
    }

    worker.project(client, FakeStorage(), event)

    assert len(client.indexed) == 1
    indexed = client.indexed[0]
    assert indexed["index"] == "signalchord-articles"
    assert indexed["id"] == "tenant-a:doc-1"
    assert indexed["refresh"] is False
    assert indexed["body"]["tenant_id"] == "tenant-a"
    assert indexed["body"]["document_id"] == "doc-1"
    assert indexed["body"]["source_id"] == "source-1"


def test_source_takedown_deletes_only_matching_tenant_source_articles() -> None:
    client = FakeSearchClient()

    worker.project(
        client,
        None,
        {
            "event_type": "source.takedown.requested.v1",
            "tenant_id": "tenant-a",
            "payload": {"source_id": "source-1"},
        },
    )

    assert client.deleted == [
        {
            "index": "signalchord-articles",
            "body": {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"tenant_id": "tenant-a"}},
                            {"term": {"source_id": "source-1"}},
                        ]
                    }
                }
            },
            "refresh": True,
            "conflicts": "proceed",
        }
    ]


def test_entity_and_claim_projection_use_tenant_prefixed_ids() -> None:
    client = FakeSearchClient()

    worker.project(
        client,
        None,
        {
            "event_type": "entity.resolved.v1",
            "tenant_id": "tenant-a",
            "payload": {
                "entity_id": "entity-1",
                "display_name": "Entity",
                "entity_type": "Organization",
                "confidence": 0.9,
                "status": "resolved",
            },
        },
    )
    worker.project(
        client,
        None,
        {
            "event_type": "claim.clustered.v1",
            "tenant_id": "tenant-a",
            "payload": {
                "claim_id": "claim-1",
                "cluster_id": "cluster-1",
                "proposition": "A claim",
                "stance": "supporting",
                "confidence": 0.8,
            },
        },
    )

    assert [item["id"] for item in client.indexed] == ["tenant-a:entity-1", "tenant-a:claim-1"]
    assert all(item["body"]["tenant_id"] == "tenant-a" for item in client.indexed)
