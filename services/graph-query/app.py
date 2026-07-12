from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "signalchord-dev")


class PathRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    from_id: str = Field(min_length=1, max_length=256)
    to_id: str = Field(min_length=1, max_length=256)
    max_depth: int = Field(default=4, ge=1, le=6)


def serialize(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: serialize(item) for key, item in dict(value).items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    app.state.driver.verify_connectivity()
    yield
    app.state.driver.close()


app = FastAPI(title="SignalChord Graph Query", version="1.0.0", lifespan=lifespan)


def records(query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    with app.state.driver.session() as session:
        result = session.run(query, parameters)
        return [serialize(record.data()) for record in result]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    rows = records("RETURN 'ok' AS status", {})
    return {"status": rows[0]["status"], "version": "1.0.0"}


@app.get("/v1/entities/{stable_id}")
def entity(stable_id: str, tenant_id: str = Query(min_length=1, max_length=128)) -> dict[str, Any]:
    rows = records(
        """
        MATCH (entity:Entity {stable_id: $stable_id})
        WHERE entity.tenant_id IS NULL OR entity.tenant_id = $tenant_id
        OPTIONAL MATCH (evidence:Evidence)-[:EVIDENCE_FOR]->(entity)
        OPTIONAL MATCH (article:Article)-[mention:MENTIONS]->(entity)
        RETURN properties(entity) AS entity,
               collect(DISTINCT properties(evidence))[0..50] AS evidence,
               collect(DISTINCT {article: properties(article), relationship: properties(mention)})[0..50] AS mentions
        """,
        {"stable_id": stable_id, "tenant_id": tenant_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="entity_not_found")
    return rows[0]


@app.get("/v1/entities/{stable_id}/timeline")
def entity_timeline(
    stable_id: str,
    tenant_id: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=100, ge=1, le=250),
) -> dict[str, Any]:
    rows = records(
        """
        MATCH (entity:Entity {stable_id: $stable_id})
        WHERE entity.tenant_id IS NULL OR entity.tenant_id = $tenant_id
        MATCH (article:Article)-[relationship:MENTIONS|ABOUT|AFFECTS]->(entity)
        WHERE article.tenant_id IS NULL OR article.tenant_id = $tenant_id
        OPTIONAL MATCH (article)-[:MAKES_CLAIM]->(claim:Claim)
        RETURN properties(article) AS article,
               properties(relationship) AS relationship,
               collect(DISTINCT properties(claim))[0..20] AS claims
        ORDER BY coalesce(article.published_at, article.observed_at) DESC
        LIMIT $limit
        """,
        {"stable_id": stable_id, "tenant_id": tenant_id, "limit": limit},
    )
    return {"entity_id": stable_id, "items": rows}


@app.get("/v1/entities/{stable_id}/graph")
def entity_graph(
    stable_id: str,
    tenant_id: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=100, ge=1, le=250),
    min_confidence: float = Query(default=0, ge=0, le=1),
) -> dict[str, Any]:
    rows = records(
        """
        MATCH (root:Entity {stable_id: $stable_id})
        WHERE root.tenant_id IS NULL OR root.tenant_id = $tenant_id
        MATCH (root)-[relationship]-(neighbor)
        WHERE (neighbor.tenant_id IS NULL OR neighbor.tenant_id = $tenant_id)
          AND coalesce(relationship.confidence, 1.0) >= $min_confidence
        RETURN properties(root) AS root,
               type(relationship) AS relationship_type,
               properties(relationship) AS relationship,
               labels(neighbor) AS neighbor_labels,
               properties(neighbor) AS neighbor
        LIMIT $limit
        """,
        {
            "stable_id": stable_id,
            "tenant_id": tenant_id,
            "limit": limit,
            "min_confidence": min_confidence,
        },
    )
    if not rows:
        entity(stable_id, tenant_id)
    return {"root_id": stable_id, "edges": rows, "truncated": len(rows) == limit}


@app.post("/v1/paths")
def paths(request: PathRequest) -> dict[str, Any]:
    depth = request.max_depth
    query = f"""
        MATCH (source {{stable_id: $from_id}}), (target {{stable_id: $to_id}})
        WHERE (source.tenant_id IS NULL OR source.tenant_id = $tenant_id)
          AND (target.tenant_id IS NULL OR target.tenant_id = $tenant_id)
        MATCH path = shortestPath((source)-[*..{depth}]-(target))
        WHERE all(node IN nodes(path) WHERE node.tenant_id IS NULL OR node.tenant_id = $tenant_id)
        RETURN [node IN nodes(path) | {{labels: labels(node), properties: properties(node)}}] AS nodes,
               [relationship IN relationships(path) | {{type: type(relationship), properties: properties(relationship)}}] AS relationships
        LIMIT 5
    """
    return {
        "from_id": request.from_id,
        "to_id": request.to_id,
        "paths": records(
            query,
            {"from_id": request.from_id, "to_id": request.to_id, "tenant_id": request.tenant_id},
        ),
    }
