import json
import os

import pytest

from app.config import PROJECT_ROOT, Settings
from app.services.qa import GraphAnswerEngine
from app.services.research import ResearchService
from app.services.snapshot import SnapshotManager

RESEARCH_VERSION = os.environ.get(
    "VITAK_TEST_RESEARCH_SNAPSHOT",
    "vitak-research-2026.11-t02",
)
EVAL_VERSION = "eval-two-group-2026-11-25"


@pytest.fixture(scope="module")
def research_context():
    root = PROJECT_ROOT / "data" / "snapshots" / RESEARCH_VERSION
    if not (root / "manifest.json").exists():
        pytest.skip("real research snapshot is not available in this checkout")
    settings = Settings(
        data_dir=PROJECT_ROOT / "data",
        research_snapshot_version=RESEARCH_VERSION,
        _env_file=None,
    )
    try:
        context = SnapshotManager(settings).open(RESEARCH_VERSION)
    except RuntimeError as error:
        if "lock" in str(error).lower():
            pytest.skip("research snapshot is currently locked by a running API")
        raise
    yield settings, context
    context.close()


@pytest.fixture(scope="module")
def eval_context():
    root = PROJECT_ROOT / "data" / "snapshots" / EVAL_VERSION
    if not (root / "manifest.json").exists():
        pytest.skip("isolated two-group evaluation snapshot is not available")
    settings = Settings(
        data_dir=PROJECT_ROOT / "data",
        research_snapshot_version=EVAL_VERSION,
        _env_file=None,
    )
    try:
        context = SnapshotManager(settings).open(EVAL_VERSION)
    except RuntimeError as error:
        if "lock" in str(error).lower():
            pytest.skip("evaluation snapshot is currently locked")
        raise
    yield settings, context
    context.close()


def test_research_overview_uses_overlapping_set_definitions(research_context):
    settings, context = research_context
    overview = ResearchService(settings, context).overview()

    assert overview.total_internal_records == 248
    assert overview.core_records == 48
    assert overview.contextual_records == 160
    assert overview.core_contextual_overlap == 9
    assert overview.grade_distribution == {
        "Negative": 179,
        "A": 31,
        "B": 10,
        "C": 28,
    }


def test_research_filters_and_internal_citations(research_context):
    settings, context = research_context
    service = ResearchService(settings, context)

    filtered = service.search(
        collection="contextual",
        test_family="sex_interaction",
        outcome="HOMA-IR",
        page_size=50,
    )
    assert filtered.total > 0
    assert all(item.data_origin == "internal" for item in filtered.items)
    assert all(item.access_scope == "private" for item in filtered.items)
    assert all(item.test_family == "sex_interaction" for item in filtered.items)

    answer = service.answer(
        "内部队列中VK1和HOMA-IR有什么关系？",
        persist=False,
    )
    assert answer.claims
    assert answer.citations
    assert all(citation.data_origin == "internal" for citation in answer.citations)
    assert all(citation.access_scope == "private" for citation in answer.citations)
    assert all(citation.id in {
        evidence_id
        for claim in answer.claims
        for evidence_id in claim.evidence_ids
    } for citation in answer.citations)


def test_domain_engine_excludes_internal_evidence(research_context):
    settings, context = research_context
    answer = GraphAnswerEngine(settings, context).answer(
        "内部队列中VK1和HOMA-IR有什么关系？",
        source_types={"literature", "structured"},
    )

    assert all(citation.data_origin != "internal" for citation in answer.citations)


def test_domain_engine_rejects_out_of_scope_question_on_real_snapshot(
    research_context,
):
    settings, context = research_context
    answer = GraphAnswerEngine(settings, context).answer(
        "维生素K能预测明天天气吗？",
        source_types={"literature", "structured"},
        persist=False,
    )

    assert answer.sufficiency == "none"
    assert answer.claims == []
    assert answer.citations == []


def test_all_ten_no_evidence_questions_are_refused(eval_context):
    settings, context = eval_context
    question_path = PROJECT_ROOT / "data/eval/two-group-questions-2026-11-25.jsonl"
    questions = [
        json.loads(line)
        for line in question_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    refusal_questions = [
        question for question in questions if question["expect_no_evidence"]
    ]
    engine = GraphAnswerEngine(settings, context)

    answers = [
        engine.answer(question["query"], persist=False)
        for question in refusal_questions
    ]

    assert len(answers) == 10
    assert all(answer.sufficiency == "none" for answer in answers)
    assert all(answer.claims == [] for answer in answers)
    assert all(answer.citations == [] for answer in answers)


def test_multi_hop_answers_with_expected_evidence_include_real_paths(eval_context):
    settings, context = eval_context
    question_path = PROJECT_ROOT / "data/eval/two-group-questions-2026-11-25.jsonl"
    questions = {
        question["id"]: question
        for question in (
            json.loads(line)
            for line in question_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    engine = GraphAnswerEngine(settings, context)

    for question_id in [
        "q-061",
        "q-062",
        "q-064",
        "q-065",
        "q-066",
        "q-068",
        "q-069",
    ]:
        question = questions[question_id]
        answer = engine.answer(question["query"], persist=False)
        path_evidence = {
            evidence_id
            for path in answer.graph_paths
            for evidence_id in path.evidence_ids
        }
        assert answer.graph_paths, question_id
        assert path_evidence.intersection(question["expected_evidence_ids"]), question_id

    for question_id in ["q-063", "q-067"]:
        question = questions[question_id]
        answer = engine.answer(question["query"], persist=False)
        citation_ids = {citation.id for citation in answer.citations}
        path_evidence = {
            evidence_id
            for path in answer.graph_paths
            for evidence_id in path.evidence_ids
        }
        assert answer.graph_paths, question_id
        assert path_evidence
        assert path_evidence.intersection(citation_ids), question_id


def test_metadata_descriptions_never_become_formal_answer_evidence(eval_context):
    settings, context = eval_context
    answer = GraphAnswerEngine(settings, context).answer(
        "菠菜和维生素K1有什么关系？",
        persist=False,
    )

    assert answer.claims
    assert answer.citations
    assert answer.graph_paths
    assert "杏仁" not in answer.answer_text
    assert "CN_FOOD_COMPOSITION" not in answer.answer_text
    assert all("Description" not in citation.locator for citation in answer.citations)
    assert any(
        "spinach" in f"{citation.locator} {citation.snippet}".lower()
        for citation in answer.citations
    )


def test_vitamin_k1_and_k2_comparison_uses_form_evidence(eval_context):
    settings, context = eval_context
    answer = GraphAnswerEngine(settings, context).answer(
        "维生素K1和K2有什么区别？",
        persist=False,
    )

    assert answer.sufficiency == "sufficient"
    assert answer.intent == "comparison"
    assert len(answer.claims) >= 3
    assert answer.citations
    assert "没有找到足够可靠" not in answer.answer_text
    assert "K2内部" in answer.answer_text
