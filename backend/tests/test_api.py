from fastapi.testclient import TestClient

from app.main import app


def test_public_api_contract_and_internal_auth():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        answer = client.post(
            "/api/v1/qa/query",
            json={"query": "维生素K有哪些食物来源？"},
        )
        evidence_search = client.get(
            "/api/v1/search",
            params={"q": "维生素K", "limit": 5},
        )
        graph_search = client.get("/api/v1/graph/search", params={"q": "Vitamin K"})
        entity_ids = [item["id"] for item in graph_search.json()["items"][:1]]
        graph = client.post(
            "/api/v1/graph/subgraph",
            json={"entity_ids": entity_ids, "depth": 1},
        )
        full_graph = client.post("/api/v1/graph/full", json={})
        protected = client.post(
            "/internal/v1/ingest",
            json={"path": "/tmp/does-not-exist.txt"},
        )

    assert health.status_code == 200
    assert health.json()["runtime_llm"] is False
    assert answer.status_code == 200
    assert answer.json()["claims"]
    assert evidence_search.status_code == 200
    search_items = evidence_search.json()["items"]
    assert search_items
    assert search_items[0]["evidence_json"]
    assert search_items[0]["evidence_json"]["source_id"] == search_items[0]["source_id"]
    assert all(
        citation["data_origin"]
        in {"internal", "external", "public", "synthetic"}
        for citation in answer.json()["citations"]
    )
    assert graph_search.status_code == 200
    assert entity_ids
    assert graph.status_code == 200
    assert graph.json()["nodes"]
    assert full_graph.status_code == 200
    assert full_graph.json()["nodes"]
    assert len(full_graph.json()["nodes"]) >= len(graph.json()["nodes"])
    assert full_graph.json()["edges"]
    assert protected.status_code == 401
