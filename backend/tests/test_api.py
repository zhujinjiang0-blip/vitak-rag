from fastapi.testclient import TestClient

from app.main import app


def test_public_api_contract_and_internal_auth():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        answer = client.post(
            "/api/v1/qa/query",
            json={"query": "维生素K有哪些食物来源？"},
        )
        graph = client.post(
            "/api/v1/graph/subgraph",
            json={"entity_ids": ["vitamin-k"], "depth": 1},
        )
        protected = client.post(
            "/internal/v1/ingest",
            json={"path": "/tmp/does-not-exist.txt"},
        )

    assert health.status_code == 200
    assert health.json()["runtime_llm"] is False
    assert answer.status_code == 200
    assert answer.json()["claims"]
    assert {
        citation["data_origin"] for citation in answer.json()["citations"]
    }.issubset({"public", "synthetic"})
    assert graph.status_code == 200
    assert graph.json()["nodes"]
    assert protected.status_code == 401
