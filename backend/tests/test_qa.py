from app.schemas import EvidenceSufficiency


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
