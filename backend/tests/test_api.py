from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings
from app.schemas import UserRole
from app.services.auth import AuthStore
from app.services.snapshot import DEMO_VERSION, SnapshotManager


def test_public_api_contract_and_internal_auth(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    manager = SnapshotManager(settings)
    manager.create_demo_snapshot()
    manager.activate(DEMO_VERSION)
    auth = AuthStore(settings.resolved_auth_db_path)
    auth.create_user(
        "admin",
        "research-pass",
        display_name="测试管理员",
        role=UserRole.ADMIN,
    )
    auth.create_user(
        "researcher",
        "research-pass",
        display_name="测试研究员",
        role=UserRole.RESEARCHER,
    )
    monkeypatch.setattr(main_module, "settings", settings)

    with TestClient(main_module.app) as client:
        health = client.get("/api/v1/health")
        session_before_login = client.get("/api/v1/auth/session")
        answer = client.post(
            "/api/v1/qa/query",
            json={"query": "维生素K有哪些食物来源？"},
        )
        evidence_search = client.get(
            "/api/v1/search",
            params={"q": "维生素K", "limit": 5},
        )
        internal_search = client.get(
            "/api/v1/search",
            params={"q": "Vitamin K", "origin": "internal", "limit": 5},
        )
        protected_overview = client.get("/api/v1/research/overview")
        protected_insights = client.get("/api/v1/research/insights")
        protected = client.post(
            "/internal/v1/ingest",
            json={"path": "/tmp/does-not-exist.txt"},
        )
        no_evidence = client.post(
            "/api/v1/qa/query",
            json={"query": "维生素K能预测明天天气吗？"},
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "research-pass"},
        )
        me = client.get("/api/v1/auth/me")
        session_after_login = client.get("/api/v1/auth/session")
        internal_search_authorized = client.get(
            "/api/v1/search",
            params={"q": "Vitamin K", "origin": "internal", "limit": 5},
        )
        research_evidence = client.get(
            "/api/v1/research/evidence",
            params={"page_size": 1},
        )
        internal_evidence_id = research_evidence.json()["items"][0]["evidence_json"][
            "evidence_id"
        ]
        internal_evidence_authorized = client.get(
            f"/api/v1/evidence/{internal_evidence_id}"
        )
        research_overview = client.get("/api/v1/research/overview")
        research_insights = client.get("/api/v1/research/insights")
        research_answer = client.post(
            "/api/v1/qa/query",
            json={"query": "内部队列中维生素K与血糖有什么关系？", "mode": "research"},
        )
        graph_search = client.get("/api/v1/graph/search", params={"q": "Vitamin K"})
        chinese_graph_search = client.get(
            "/api/v1/graph/search",
            params={"q": "华法林"},
        )
        entity_ids = [item["id"] for item in graph_search.json()["items"][:1]]
        graph = client.post(
            "/api/v1/graph/subgraph",
            json={"entity_ids": entity_ids, "depth": 1},
        )
        full_graph = client.post("/api/v1/graph/full", json={})
        snapshots = client.get("/internal/v1/snapshots")
        active_audit = client.get("/internal/v1/governance/active")
        unknown_audit = client.get(
            "/internal/v1/governance/snapshots/not-a-snapshot"
        )
        same_version_diff = client.get(
            "/internal/v1/governance/diff",
            params={
                "from_version": DEMO_VERSION,
                "to_version": DEMO_VERSION,
            },
        )
        feedback = client.post(
            "/api/v1/feedback/unmet",
            json={
                "query": "当前库是否有未收录的维生素K研究？",
                "mode": "domain",
                "reason": "knowledge_gap",
                "data_scope": ["external"],
            },
        )
        unmet_needs = client.get("/internal/v1/unmet-needs")
        audit_logs = client.get("/internal/v1/audit-logs")
        logout = client.post("/api/v1/auth/logout")
        me_after_logout = client.get("/api/v1/auth/me")
        internal_evidence_anonymous = client.get(
            f"/api/v1/evidence/{internal_evidence_id}"
        )
        researcher_login = client.post(
            "/api/v1/auth/login",
            json={"username": "researcher", "password": "research-pass"},
        )
        researcher_admin_action = client.get("/internal/v1/snapshots")

    assert health.status_code == 200
    assert session_before_login.status_code == 200
    assert session_before_login.json() is None
    assert health.json()["runtime_llm"] is False
    assert health.json()["llm_configured"] is False
    assert health.json()["llm_endpoint_class"] == "cloud_public"
    assert health.json()["llm_protected_evidence_allowed"] is False
    assert "api_key" not in health.text.lower()
    assert answer.status_code == 200
    assert answer.json()["claims"]
    assert answer.json()["generation"]["status"] == "disabled"
    assert evidence_search.status_code == 200
    search_items = evidence_search.json()["items"]
    assert search_items
    assert search_items[0]["evidence_json"]
    assert search_items[0]["evidence_json"]["source_id"] == search_items[0]["source_id"]
    assert internal_search.status_code == 401
    assert protected_overview.status_code == 401
    assert protected_insights.status_code == 401
    assert no_evidence.status_code == 200
    assert no_evidence.json()["sufficiency"] == "none"
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"
    assert me.status_code == 200
    assert session_after_login.status_code == 200
    assert session_after_login.json()["role"] == "admin"
    assert internal_search_authorized.status_code == 200
    assert all(
        item["data_origin"] == "internal"
        for item in internal_search_authorized.json()["items"]
    )
    assert internal_evidence_authorized.status_code == 200
    assert research_evidence.status_code == 200
    assert research_overview.status_code == 200
    assert research_overview.json()["data_scope"] == "internal/private"
    assert research_insights.status_code == 200
    assert research_insights.json()["total_records"] >= 1
    assert research_insights.json()["status_distribution"]
    assert research_answer.status_code == 200
    assert research_answer.json()["mode"] == "research"
    assert all(
        citation["access_scope"] == "private"
        for citation in research_answer.json()["citations"]
    )
    assert all(
        citation["data_origin"]
        in {"internal", "external", "public", "synthetic"}
        for citation in answer.json()["citations"]
    )
    assert graph_search.status_code == 200
    assert chinese_graph_search.status_code == 200
    assert chinese_graph_search.json()["items"]
    assert entity_ids
    assert graph.status_code == 200
    assert graph.json()["nodes"]
    assert full_graph.status_code == 200
    assert full_graph.json()["nodes"]
    assert len(full_graph.json()["nodes"]) >= len(graph.json()["nodes"])
    assert full_graph.json()["edges"]
    assert snapshots.status_code == 200
    assert snapshots.json()["items"]
    assert active_audit.status_code == 200
    assert active_audit.json()["active"] is True
    assert active_audit.json()["checks"]
    assert unknown_audit.status_code == 404
    assert same_version_diff.status_code == 200
    assert all(
        delta == 0 for delta in same_version_diff.json()["count_deltas"].values()
    )
    assert feedback.status_code == 200
    assert feedback.json()["reason"] == "knowledge_gap"
    assert unmet_needs.status_code == 200
    assert unmet_needs.json()["total"] >= 2
    assert audit_logs.status_code == 200
    assert protected.status_code == 401
    assert logout.status_code == 200
    assert me_after_logout.status_code == 401
    assert internal_evidence_anonymous.status_code == 404
    assert researcher_login.status_code == 200
    assert researcher_admin_action.status_code == 403
