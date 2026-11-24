import json

import httpx
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings
from app.schemas import GenerationStatus, QAMode
from app.services.qa_orchestrator import RuntimeQAService
from app.services.runtime_llm import (
    DraftAnswer,
    DraftClaim,
    ParsedQuestion,
    RuntimeLLMClient,
    RuntimeLLMEvidenceBlocked,
)


class FakeRuntimeLLM:
    configured = True
    available = True
    provider = "fake"
    model = "fake-evidence-model"

    def __init__(self, *, invalid_number: bool = False):
        self.invalid_number = invalid_number
        self.parse_calls = 0
        self.generate_calls = 0

    def parse_question(self, query, *, mode, candidate_entities, filters):
        self.parse_calls += 1
        return ParsedQuestion(
            intent="food_sources",
            entities=["维生素K"],
            filters={},
            confidence=0.92,
        )

    def generate_answer(
        self,
        *,
        query,
        mode,
        deterministic_answer,
        evidence,
    ):
        self.generate_calls += 1
        claims = []
        for claim in deterministic_answer["claims"]:
            text = claim["text"]
            if self.invalid_number:
                text = f"{text} 可完全降低风险 999%。"
            claims.append(
                DraftClaim(
                    text=text,
                    evidence_ids=claim["evidence_ids"],
                    claim_type=claim["claim_type"],
                )
            )
        return DraftAnswer(
            opening="可以从现有证据来理解。",
            claims=claims,
            closing="这些结论仍需结合研究条件和证据边界阅读。",
        )


def test_runtime_llm_client_parses_openai_compatible_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-chat"
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"intent":"research","entities":["MK-7"],'
                                '"filters":{"test_family":"postprandial"},'
                                '"confidence":0.91,'
                                '"requires_clarification":false}'
                            )
                        }
                    }
                ]
            },
        )

    settings = Settings(
        runtime_llm_enabled=True,
        runtime_llm_api_key="test-key",
        runtime_llm_base_url="https://api.deepseek.com/v1",
        runtime_llm_model="deepseek-chat",
        _env_file=None,
    )
    client = RuntimeLLMClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    parsed = client.parse_question(
        "内部队列里MK-7餐后结果如何？",
        mode="research",
        candidate_entities=[{"name": "MK-7", "id": "mk-7"}],
        filters={},
    )

    assert parsed is not None
    assert parsed.intent == "research"
    assert parsed.entities == ["MK-7"]
    assert parsed.filters["test_family"] == "postprandial"


def test_grounded_generation_persists_only_validated_claims(engine):
    fake = FakeRuntimeLLM()
    service = RuntimeQAService(engine.settings, engine.snapshot, llm=fake)

    answer = service.answer(
        "维生素K有哪些食物来源？",
        session_id=None,
        mode=QAMode.DOMAIN,
        filters={},
    )

    assert fake.parse_calls == 1
    assert fake.generate_calls == 1
    assert answer.generation.status == GenerationStatus.GENERATED
    assert answer.generation.used is True
    assert answer.generation.verification == "passed"
    assert answer.claims
    assert all(claim.evidence_ids for claim in answer.claims)
    citation_ids = {citation.id for citation in answer.citations}
    assert all(
        evidence_id in citation_ids
        for claim in answer.claims
        for evidence_id in claim.evidence_ids
    )
    messages = engine.metadata.get_recent_messages(answer.session_id, limit=4)
    assert [message["role"] for message in messages[-2:]] == ["user", "assistant"]


def test_generated_unsupported_number_falls_back_to_deterministic_answer(engine):
    fake = FakeRuntimeLLM(invalid_number=True)
    service = RuntimeQAService(engine.settings, engine.snapshot, llm=fake)

    answer = service.answer(
        "维生素K有哪些食物来源？",
        session_id=None,
        mode=QAMode.DOMAIN,
        filters={},
    )

    assert answer.generation.status == GenerationStatus.FALLBACK
    assert answer.generation.used is False
    assert answer.generation.verification == "failed"
    assert "999%" not in answer.answer_text
    assert answer.claims


def test_disabled_runtime_llm_keeps_deterministic_answer(engine):
    service = RuntimeQAService(engine.settings, engine.snapshot)

    answer = service.answer(
        "维生素K有哪些食物来源？",
        session_id=None,
        mode=QAMode.DOMAIN,
        filters={},
    )

    assert answer.generation.status == GenerationStatus.DISABLED
    assert answer.generation.configured is False
    assert answer.generation.used is False
    assert answer.claims


def test_stream_api_exposes_runtime_generation_status(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    monkeypatch.setattr(main_module, "settings", settings)

    with TestClient(main_module.app) as client:
        main_module.app.state.runtime_llm = FakeRuntimeLLM()
        response = client.post(
            "/api/v1/qa/stream",
            json={"query": "维生素K有哪些食物来源？", "mode": "domain"},
        )

    assert response.status_code == 200
    assert "event: generation" in response.text
    assert '"used": true' in response.text
    assert "event: done" in response.text


def test_cloud_endpoint_blocks_protected_evidence_without_http_request():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    settings = Settings(
        runtime_llm_enabled=True,
        runtime_llm_api_key="test-key",
        runtime_llm_base_url="https://api.deepseek.com/v1",
        runtime_llm_endpoint_class="cloud_public",
        runtime_llm_allow_protected_evidence=True,
        _env_file=None,
    )
    client = RuntimeLLMClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.generate_answer(
            query="内部队列结果如何？",
            mode="research",
            deterministic_answer={
                "claims": [
                    {
                        "evidence_ids": ["internal-evidence"],
                    }
                ]
            },
            evidence=[
                {
                    "id": "internal-evidence",
                    "data_origin": "internal",
                    "access_scope": "private",
                    "snippet": "内部统计结果",
                }
            ],
        )
    except RuntimeLLMEvidenceBlocked:
        pass
    else:
        raise AssertionError("protected evidence should have been blocked")

    assert calls == 0


def test_private_network_endpoint_can_process_protected_evidence():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"opening":"内部结果如下。","claims":['
                                '{"text":"内部分析未观察到显著关联。",'
                                '"evidence_ids":["internal-evidence"],'
                                '"claim_type":"negative"}],"closing":"需专业评估。"}'
                            )
                        }
                    }
                ]
            },
        )

    settings = Settings(
        runtime_llm_enabled=True,
        runtime_llm_api_key="test-key",
        runtime_llm_base_url="http://127.0.0.1:9999/v1",
        runtime_llm_endpoint_class="private_network",
        runtime_llm_allow_protected_evidence=True,
        _env_file=None,
    )
    client = RuntimeLLMClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    draft = client.generate_answer(
        query="内部队列结果如何？",
        mode="research",
        deterministic_answer={
            "claims": [
                {
                    "evidence_ids": ["internal-evidence"],
                }
            ]
        },
        evidence=[
            {
                "id": "internal-evidence",
                "data_origin": "internal",
                "access_scope": "private",
                "snippet": "内部统计结果",
            }
        ],
    )

    assert draft is not None
    assert calls == 1
    assert client.protected_evidence_allowed is True


def test_cloud_endpoint_sends_only_explicit_public_evidence():
    seen_scope = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_scope
        request_body = json.loads(request.content)
        payload = json.loads(request_body["messages"][1]["content"])
        seen_scope = payload["evidence"][0]["access_scope"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"opening":"公开证据如下。","claims":['
                                '{"text":"维生素K1与K2属于不同形式。",'
                                '"evidence_ids":["public-evidence"],'
                                '"claim_type":"general"}],"closing":"需结合原始证据。"}'
                            )
                        }
                    }
                ]
            },
        )

    settings = Settings(
        runtime_llm_enabled=True,
        runtime_llm_api_key="test-key",
        runtime_llm_base_url="https://api.deepseek.com/v1",
        runtime_llm_endpoint_class="cloud_public",
        _env_file=None,
    )
    client = RuntimeLLMClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    draft = client.generate_answer(
        query="维生素K1和K2有什么区别？",
        mode="domain",
        deterministic_answer={
            "claims": [{"evidence_ids": ["public-evidence"]}]
        },
        evidence=[
            {
                "id": "public-evidence",
                "data_origin": "external",
                "access_scope": "public",
                "snippet": "公开文献证据",
            }
        ],
    )

    assert draft is not None
    assert seen_scope == "public"


def test_public_only_model_skips_research_and_comparison(engine):
    fake = FakeRuntimeLLM()
    service = RuntimeQAService(engine.settings, engine.snapshot, llm=fake)

    research = service.answer(
        "内部队列中VK1和HOMA-IR有什么关系？",
        session_id=None,
        mode=QAMode.RESEARCH,
        filters={},
    )
    comparison = service.answer(
        "维生素K有哪些食物来源？",
        session_id=None,
        mode=QAMode.COMPARISON,
        filters={},
    )

    assert research.generation.used is False
    assert comparison.generation.used is False
    assert "public-only" in research.generation.fallback_reason
    assert "public-only" in comparison.generation.fallback_reason
    assert fake.parse_calls == 0
    assert fake.generate_calls == 0
