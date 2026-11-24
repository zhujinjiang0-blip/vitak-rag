import json

from app.cli import _write_evaluation_artifacts
from app.services.evaluation import EvaluationQuestion, EvaluationService
from app.services.evidence_tables import file_sha256


def test_evaluation_uses_plain_rag_and_kg_hybrid_only(demo_context):
    settings, _, context = demo_context
    service = EvaluationService(settings, context)

    report = service.run([])

    assert report["experiment"] == "plain_rag_vs_kg_hybrid"
    assert set(report["summary"]) == {"plain_rag", "kg_hybrid"}


def test_plain_rag_combines_keyword_and_semantic_candidates(demo_context):
    settings, _, context = demo_context
    service = EvaluationService(settings, context)

    evidence_ids = service._plain_rag_hits("维生素K有哪些食物来源？")

    assert evidence_ids
    assert len(evidence_ids) == len(set(evidence_ids))


def test_keyword_retrieval_order_is_stable(demo_context):
    settings, _, context = demo_context
    service = EvaluationService(settings, context)

    first = service._keyword_hits("维生素K食物来源", limit=20)
    second = service._keyword_hits("维生素K食物来源", limit=20)

    assert first == second


def test_path_metric_is_not_applicable_without_explicit_graph_paths():
    question = EvaluationQuestion(
        id="q-path",
        query="多跳问题",
        intent="multi_hop",
        expected_evidence_ids=["evidence-1"],
    )

    score = EvaluationService._score(
        question,
        ["evidence-1"],
        10,
        refused=False,
        path_evidence=None,
    )

    assert score["recall_at_5"] == 1.0
    assert score["path_hit_rate"] is None


def test_multi_hop_without_expected_path_matches_q070_semantics():
    question = EvaluationQuestion(
        id="q-070",
        query="PT和INR如何用于凝血评估？",
        intent="multi_hop",
        expected_evidence_ids=[],
        expected_path_evidence_ids=[],
    )

    score = EvaluationService._score(
        question,
        [],
        10,
        refused=True,
        path_evidence=None,
    )

    assert score["path_hit_rate"] is None


def test_path_metric_uses_explicit_expected_paths():
    question = EvaluationQuestion(
        id="q-path",
        query="多跳问题",
        intent="multi_hop",
        expected_evidence_ids=["evidence-1"],
        expected_path_evidence_ids=["path-evidence"],
    )

    score = EvaluationService._score(
        question,
        ["evidence-1"],
        10,
        refused=False,
        path_evidence=["path-evidence"],
    )

    assert score["path_hit_rate"] == 1.0


def test_no_evidence_uses_refusal_metric_without_fake_retrieval_score():
    question = EvaluationQuestion(
        id="q-refusal",
        query="无证据问题",
        intent="no_evidence",
        expect_no_evidence=True,
    )

    score = EvaluationService._score(
        question,
        [],
        5,
        refused=True,
        path_evidence=None,
    )

    assert score["refusal_correct"] == 1.0
    assert score["recall_at_5"] is None
    assert score["path_hit_rate"] is None


def test_evaluation_artifacts_write_only_to_tmp_paths(tmp_path):
    output = tmp_path / "report.json"
    manifest = tmp_path / "report.manifest.json"
    report = {
        "generated_at": "2026-11-25T00:00:00+00:00",
        "inputs": {},
        "reproducibility": {},
    }

    digest = _write_evaluation_artifacts(report, output, manifest)

    saved = json.loads(output.read_text(encoding="utf-8"))
    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["generated_at"] == report["generated_at"]
    assert digest == file_sha256(output)
    assert saved_manifest["report"]["sha256"] == digest
    assert not (tmp_path.parent / "report-two-group-2026-11-25.json").exists()
