import pytest

from app.schemas import Citation, Claim, ClaimType, EvidenceSufficiency
from app.services.qa import build_evidence_comparisons, claim_science_profile


def test_claim_science_boundaries_distinguish_association_negative_and_mechanism():
    association = claim_science_profile(
        "cross_sectionally_associated_with",
        "VK1与HOMA-IR存在横断面关联。",
    )
    negative = claim_science_profile(
        "no_significant_association_observed_with",
        "未观察到MK-7与HOMA-IR的显著关联。",
    )
    mechanism = claim_science_profile(
        "activates_protein",
        "维生素K参与骨钙素活化。",
    )
    conflict = claim_science_profile(
        "evidence_synthesis",
        "现有研究结论并不完全一致。",
    )

    assert association[0] == ClaimType.ASSOCIATION
    assert "不等同于干预" in (association[1] or "")
    assert negative[0] == ClaimType.NEGATIVE
    assert "不等于证明" in (negative[1] or "")
    assert mechanism[0] == ClaimType.MECHANISM
    assert "不能直接推导" in (mechanism[1] or "")
    assert conflict[0] == ClaimType.CONFLICT
    assert "分别解释" in (conflict[1] or "")


def test_evidence_comparison_preserves_negative_and_condition_differences():
    claims = [
        Claim(
            id="claim-positive",
            text="VK1与HOMA-IR存在横断面关联。",
            evidence_ids=["E1"],
            relation="cross_sectionally_associated_with",
            claim_type=ClaimType.ASSOCIATION,
        ),
        Claim(
            id="claim-negative",
            text="未观察到MK-7与HOMA-IR的显著关联。",
            evidence_ids=["E2"],
            relation="no_significant_association_observed_with",
            claim_type=ClaimType.NEGATIVE,
        ),
    ]
    citations = [
        Citation(
            id="E1",
            source_id="S1",
            source_title="Study A",
            source_type="internal",
            snippet="cross-sectional",
            analysis_context="基线横断面",
            model_type="OLS",
            sample_n="385",
        ),
        Citation(
            id="E2",
            source_id="S2",
            source_title="Study B",
            source_type="literature",
            snippet="no significant association",
            analysis_context="纵向分析",
            model_type="mixed model",
            sample_n="240",
        ),
    ]

    comparisons = build_evidence_comparisons(claims, citations)
    statuses = {comparison.status for comparison in comparisons}

    assert "significance_difference" in statuses
    assert "context_difference" in statuses


def test_food_source_answer_preserves_relation_direction(engine):
    answer = engine.answer("维生素K有哪些食物来源？")

    assert answer.intent == "food_sources"
    assert answer.sufficiency == EvidenceSufficiency.SUFFICIENT
    assert "鸡蛋含有维生素K" in answer.answer_text
    assert "维生素K含有鸡蛋" not in answer.answer_text
    assert answer.citations


def test_multi_hop_question_returns_graph_path(engine):
    answer = engine.answer("华法林和维生素K有什么关系？")

    assert answer.intent == "drug_interactions"
    assert answer.graph_paths
    assert len(answer.graph_paths[0].edges) == 2
    assert answer.citations


def test_no_evidence_question_is_refused(engine):
    answer = engine.answer("维生素K能预测明天天气吗？")

    assert answer.sufficiency == EvidenceSufficiency.NONE
    assert "没有找到足够可靠" in answer.answer_text
    assert answer.claims == []


def test_capability_question_returns_scope_without_fake_citations(engine):
    answer = engine.answer("你能回答什么问题？")

    assert answer.intent == "capabilities"
    assert "九类问题" in answer.answer_text
    assert "不会提供疾病诊断" in answer.answer_text
    assert answer.claims == []
    assert answer.citations == []


def test_medication_safety_rule_precedes_graph_retrieval(engine):
    answer = engine.answer("华法林吃多少？")

    assert answer.intent == "medication"
    assert answer.safety_notice
    assert answer.claims == []


def test_medication_safety_pattern_catches_varied_dosing_questions(engine):
    answer = engine.answer("服用华法林时应该吃多少维生素K？")

    assert answer.intent == "medication"
    assert answer.safety_notice
    assert answer.citations == []
    assert answer.graph_paths == []


@pytest.mark.parametrize(
    "query",
    [
        "我应该自己停掉抗凝药吗？",
        "我是不是得了出血病？",
        "给我开维生素K处方。",
    ],
)
def test_safety_patterns_cover_implicit_medical_requests(engine, query):
    answer = engine.answer(query, persist=False)

    assert answer.sufficiency == "none"
    assert answer.safety_notice
    assert answer.claims == []
    assert answer.citations == []


@pytest.mark.parametrize(
    "query",
    [
        "维生素K能预测明天天气吗？",
        "维生素K可以修复手机屏幕吗？",
        "服用维生素K能保证考试满分吗？",
        "维生素K能替代所有药物吗？",
        "只靠维生素K可以治愈所有疾病吗？",
        "维生素K和火星天气有什么关系？",
    ],
)
def test_out_of_scope_questions_are_refused_before_evidence_retrieval(engine, query):
    answer = engine.answer(query, persist=False)

    assert answer.sufficiency == "none"
    assert answer.claims == []
    assert answer.citations == []


def test_every_claim_has_traceable_citation(engine):
    answer = engine.answer("维生素K1和K2有什么区别？")
    citation_ids = {citation.id for citation in answer.citations}

    assert answer.claims
    assert all(claim.evidence_ids for claim in answer.claims)
    assert all(
        evidence_id in citation_ids
        for claim in answer.claims
        for evidence_id in claim.evidence_ids
    )
    assert all(citation.data_origin in {"public", "synthetic"} for citation in answer.citations)
