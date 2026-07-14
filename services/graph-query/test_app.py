from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("app.py")
SPEC = importlib.util.spec_from_file_location("signalchord_graph_query_app", MODULE_PATH)
graph_query = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(graph_query)


class FakeRecord:
    def __init__(self, data: dict):
        self._data = data

    def data(self) -> dict:
        return self._data


class FakeResult(list):
    pass


class FakeSession:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def run(self, query: str, parameters: dict):
        self.calls.append((query, parameters))
        return FakeResult(FakeRecord(row) for row in self.rows)


class FakeDriver:
    def __init__(self, session: FakeSession):
        self._session = session

    def session(self):
        return self._session


def test_entity_query_is_parameterized_and_tenant_scoped() -> None:
    session = FakeSession(
        [
            {
                "entity": {"stable_id": "entity-1", "tenant_id": "tenant-a"},
                "evidence": [],
                "mentions": [],
            }
        ]
    )
    graph_query.app.state.driver = FakeDriver(session)

    response = graph_query.entity("entity-1", tenant_id="tenant-a")

    query, parameters = session.calls[0]
    assert response["tenant_id"] == "tenant-a"
    assert parameters == {"stable_id": "entity-1", "tenant_id": "tenant-a"}
    assert "$tenant_id" in query
    assert "entity.tenant_id = $tenant_id" in query
    assert "tenant-a" not in query


def test_timeline_and_graph_queries_filter_neighbor_tenants() -> None:
    session = FakeSession([])
    graph_query.app.state.driver = FakeDriver(session)

    graph_query.entity_timeline("entity-1", tenant_id="tenant-a", limit=25)
    try:
        graph_query.entity_graph("entity-1", tenant_id="tenant-a", limit=25, min_confidence=0.5)
    except Exception:
        # Empty graph rows fall back to entity lookup; this test only inspects the graph query issued first.
        pass

    issued_queries = "\n".join(query for query, _parameters in session.calls)
    assert "related.tenant_id IS NULL OR related.tenant_id = $tenant_id" in issued_queries
    assert "neighbor.tenant_id IS NULL OR neighbor.tenant_id = $tenant_id" in issued_queries
    assert all(parameters["tenant_id"] == "tenant-a" for _query, parameters in session.calls)


def test_path_query_limits_all_nodes_to_request_tenant() -> None:
    session = FakeSession([])
    graph_query.app.state.driver = FakeDriver(session)

    graph_query.paths(
        graph_query.PathRequest(tenant_id="tenant-a", from_id="entity-a", to_id="entity-b", max_depth=3)
    )

    query, parameters = session.calls[0]
    assert parameters == {"from_id": "entity-a", "to_id": "entity-b", "tenant_id": "tenant-a"}
    assert "source.tenant_id = $tenant_id" in query
    assert "target.tenant_id = $tenant_id" in query
    assert "all(node IN nodes(path) WHERE node.tenant_id IS NULL OR node.tenant_id = $tenant_id)" in query
    assert "tenant-a" not in query
