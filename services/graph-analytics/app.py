from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from neo4j import Driver, GraphDatabase
from pydantic import BaseModel, Field

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "signalchord-dev")


class AnalysisRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=256)
    lookback_days: int = Field(default=7, ge=1, le=365)


class AnalysisResult(BaseModel):
    entity_id: str
    graph_centrality: float = Field(ge=0)
    source_diversity: int = Field(ge=0)
    relationship_changes: int = Field(ge=0)
    method: str
    evidence_path_ids: list[str]
    explanation: list[str]


def sanitize_graph_name(tenant_id: str) -> str:
    return "signalchord_" + re.sub(r"[^a-zA-Z0-9_]", "_", tenant_id)[:48] + "_" + uuid.uuid4().hex[:8]


def query_one(driver: Driver, query: str, parameters: dict[str, Any]) -> dict[str, Any]:
    with driver.session() as session:
        record = session.run(query, parameters).single()
        return dict(record) if record else {}


def gds_available(driver: Driver) -> bool:
    try:
        row = query_one(driver, "CALL gds.version() YIELD version RETURN version", {})
        return bool(row.get("version"))
    except Exception:
        return False


def gds_degree(driver: Driver, tenant_id: str, entity_id: str) -> float:
    graph_name = sanitize_graph_name(tenant_id)
    node_query = "MATCH (n:Entity) WHERE n.tenant_id = $tenant_id RETURN id(n) AS id"
    relationship_query = (
        "MATCH (a:Entity)-[r]-(b:Entity) "
        "WHERE a.tenant_id = $tenant_id AND b.tenant_id = $tenant_id "
        "RETURN id(a) AS source, id(b) AS target"
    )
    try:
        with driver.session() as session:
            session.run(
                "CALL gds.graph.project.cypher($graph_name, $node_query, $relationship_query, "
                "{parameters: {tenant_id: $tenant_id}}) YIELD graphName",
                graph_name=graph_name,
                node_query=node_query,
                relationship_query=relationship_query,
                tenant_id=tenant_id,
            ).consume()
            record = session.run(
                "CALL gds.degree.stream($graph_name) YIELD nodeId, score "
                "WITH gds.util.asNode(nodeId) AS node, score "
                "WHERE node.stable_id = $entity_id RETURN score",
                graph_name=graph_name,
                entity_id=entity_id,
            ).single()
            return float(record["score"]) if record else 0.0
    finally:
        try:
            with driver.session() as session:
                session.run("CALL gds.graph.drop($graph_name, false)", graph_name=graph_name).consume()
        except Exception:
            pass


def fallback_degree(driver: Driver, tenant_id: str, entity_id: str) -> float:
    row = query_one(
        driver,
        "MATCH (entity:Entity {stable_id: $entity_id})-[relationship]-() "
        "WHERE entity.tenant_id = $tenant_id RETURN count(relationship) AS score",
        {"tenant_id": tenant_id, "entity_id": entity_id},
    )
    return float(row.get("score", 0))


def analyze(driver: Driver, request: AnalysisRequest) -> AnalysisResult:
    entity = query_one(
        driver,
        "MATCH (entity:Entity {stable_id: $entity_id, tenant_id: $tenant_id}) RETURN entity.stable_id AS stable_id",
        request.model_dump(),
    )
    if not entity:
        raise HTTPException(status_code=404, detail="entity_not_found")

    method = "neo4j-gds-degree"
    if gds_available(driver):
        try:
            centrality = gds_degree(driver, request.tenant_id, request.entity_id)
        except Exception:
            centrality = fallback_degree(driver, request.tenant_id, request.entity_id)
            method = "cypher-degree-fallback-after-gds-error"
    else:
        centrality = fallback_degree(driver, request.tenant_id, request.entity_id)
        method = "cypher-degree-fallback"

    metrics = query_one(
        driver,
        """
        MATCH (entity:Entity {stable_id: $entity_id, tenant_id: $tenant_id})
        OPTIONAL MATCH (article:Article)-[:MENTIONS|ABOUT|AFFECTS]->(entity)
        OPTIONAL MATCH (article)-[:PUBLISHED]->(source:Source)
        WITH entity, count(DISTINCT source) AS source_diversity
        OPTIONAL MATCH (entity)-[relationship]-()
        WHERE relationship.observed_at >= datetime() - duration({days: $lookback_days})
        RETURN source_diversity,
               count(DISTINCT relationship) AS relationship_changes,
               collect(DISTINCT relationship.stable_id)[0..50] AS evidence_path_ids
        """,
        request.model_dump(),
    )
    source_diversity = int(metrics.get("source_diversity", 0))
    relationship_changes = int(metrics.get("relationship_changes", 0))
    evidence = [value for value in metrics.get("evidence_path_ids", []) if value]
    return AnalysisResult(
        entity_id=request.entity_id,
        graph_centrality=centrality,
        source_diversity=source_diversity,
        relationship_changes=relationship_changes,
        method=method,
        evidence_path_ids=evidence,
        explanation=[
            f"Centrality was calculated with {method}.",
            f"The entity is linked to {source_diversity} distinct sources.",
            f"{relationship_changes} relationship observations occurred in the last {request.lookback_days} days.",
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    app.state.driver.verify_connectivity()
    yield
    app.state.driver.close()


app = FastAPI(title="SignalChord Graph Analytics", version="1.0.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"status": "ok", "version": "1.0.0", "gds_available": gds_available(app.state.driver)}


@app.post("/v1/analyze", response_model=AnalysisResult)
def analyze_endpoint(request: AnalysisRequest) -> AnalysisResult:
    return analyze(app.state.driver, request)
