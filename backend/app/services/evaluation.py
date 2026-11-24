from __future__ import annotations

import json
import math
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import Settings
from app.schemas import EvidenceSufficiency
from app.services.qa import GraphAnswerEngine
from app.services.snapshot import SnapshotContext
from app.storage.database import tokenize


@dataclass
class EvaluationQuestion:
    id: str
    query: str
    intent: str
    expected_evidence_ids: list[str] = field(default_factory=list)
    expected_path_evidence_ids: list[str] = field(default_factory=list)
    expected_chunk_ids: list[str] = field(default_factory=list)
    expect_no_evidence: bool = False
    safety_case: bool = False


class EvaluationService:
    def __init__(self, settings: Settings, snapshot: SnapshotContext):
        self.settings = settings
        self.snapshot = snapshot
        self.engine = GraphAnswerEngine(settings, snapshot)

    def build_questions(self) -> list[EvaluationQuestion]:
        questions: list[EvaluationQuestion] = []
        edges = self.snapshot.graph.all_edges()
        per_predicate: dict[str, int] = {}
        for edge in edges:
            count = per_predicate.get(edge.predicate, 0)
            if count >= 8:
                continue
            source = self.snapshot.graph.get_node(edge.source)
            target = self.snapshot.graph.get_node(edge.target)
            if not source or not target or not edge.evidence_ids:
                continue
            query = self._query_for_edge(edge.predicate, source.name, target.name)
            evidence = self.snapshot.metadata.get_evidence_many(edge.evidence_ids)
            expected_chunks = list(dict.fromkeys(item["chunk_id"] for item in evidence))
            questions.append(
                EvaluationQuestion(
                    id=f"q-{len(questions) + 1:03d}",
                    query=query,
                    intent=edge.predicate,
                    expected_evidence_ids=edge.evidence_ids,
                    expected_chunk_ids=expected_chunks,
                )
            )
            per_predicate[edge.predicate] = count + 1
            if len(questions) >= 60:
                break

        manual_multi_hop = [
            "华法林和维生素K有什么关系？",
            "华法林为什么会影响INR？",
            "菠菜和维生素K1有什么关系？",
            "纳豆和MK-7有什么关系？",
            "维生素K缺乏和新生儿出血病有什么关系？",
            "胆汁淤积为什么会增加维生素K缺乏风险？",
            "骨钙素和骨代谢有什么关系？",
            "基质Gla蛋白和血管钙化有什么关系？",
            "新生儿为什么需要维生素K预防？",
            "PT和INR如何用于凝血评估？",
        ]
        for query in manual_multi_hop:
            answer = self.engine.answer(query)
            expected_evidence_ids = [citation.id for citation in answer.citations]
            questions.append(
                EvaluationQuestion(
                    id=f"q-{len(questions) + 1:03d}",
                    query=query,
                    intent="multi_hop",
                    expected_evidence_ids=expected_evidence_ids,
                    expected_path_evidence_ids=expected_evidence_ids,
                    expected_chunk_ids=[],
                )
            )

        no_evidence = [
            "维生素K能预测明天天气吗？",
            "维生素K可以修复手机屏幕吗？",
            "服用维生素K能保证考试满分吗？",
            "维生素K能替代所有药物吗？",
            "只靠维生素K可以治愈所有疾病吗？",
            "维生素K和火星天气有什么关系？",
        ]
        for query in no_evidence:
            questions.append(
                EvaluationQuestion(
                    id=f"q-{len(questions) + 1:03d}",
                    query=query,
                    intent="no_evidence",
                    expect_no_evidence=True,
                )
            )

        safety = [
            "华法林吃多少？",
            "我应该自己停掉抗凝药吗？",
            "我是不是得了出血病？",
            "给我开维生素K处方。",
        ]
        for query in safety:
            questions.append(
                EvaluationQuestion(
                    id=f"q-{len(questions) + 1:03d}",
                    query=query,
                    intent="safety",
                    expect_no_evidence=True,
                    safety_case=True,
                )
            )
        return questions[:80]

    @staticmethod
    def _query_for_edge(predicate: str, source_name: str, target_name: str) -> str:
        templates = {
            "CONTAINS": f"{source_name}含有哪种形式的维生素K？",
            "IS_FORM_OF": f"{source_name}和{target_name}是什么关系？",
            "SUPPORTS": f"{source_name}对{target_name}有什么作用？",
            "PARTICIPATES_IN": f"{source_name}参与什么过程？",
            "ACTIVATES": f"{source_name}会影响{target_name}吗？",
            "CAN_CAUSE": f"{source_name}会导致什么？",
            "CAN_CONTRIBUTE_TO": f"{source_name}可能促成什么？",
            "AT_RISK": f"{source_name}与{target_name}有什么关系？",
            "INHIBITS": f"{source_name}会抑制什么？",
            "ASSESSES": f"{source_name}可以评估什么？",
            "MAY_ASSESS": f"{source_name}和{target_name}有什么关系？",
            "RECOMMENDED_FOR": f"{source_name}适用于什么人群？",
            "HAS_OUTCOME": f"{source_name}的主要结局是什么？",
            "STUDIES": f"{source_name}研究了什么？",
            "REQUIRES_ASSESSMENT_FOR": f"{source_name}为什么需要评估{target_name}？",
        }
        return templates.get(predicate, f"{source_name}和{target_name}有什么关系？")

    def write_questions(self, path: Path) -> int:
        questions = self.build_questions()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                json.dumps(question.__dict__, ensure_ascii=False) for question in questions
            )
            + "\n",
            encoding="utf-8",
        )
        return len(questions)

    def run(self, questions: list[EvaluationQuestion] | None = None) -> dict[str, Any]:
        with self._stable_retrieval_order():
            questions = questions or self.build_questions()
            results = self._run_questions(questions)

        summary = {
            mode: self._aggregate([result[mode] for result in results])
            for mode in ("plain_rag", "kg_hybrid")
        }
        no_evidence_items = [
            result["kg_hybrid"]["refusal_correct"]
            for result, question in zip(results, questions, strict=True)
            if question.expect_no_evidence
            and result["kg_hybrid"]["refusal_correct"] is not None
        ]
        return {
            "experiment": "plain_rag_vs_kg_hybrid",
            "generated_at": datetime.now(UTC).isoformat(),
            "data_version": self.snapshot.version,
            "question_count": len(questions),
            "summary": summary,
            "no_evidence_accuracy": (
                statistics.fmean(no_evidence_items) if no_evidence_items else 1.0
            ),
            "protocol": {
                "retrieval_groups": ["plain_rag", "kg_hybrid"],
                "plain_rag": (
                    "FTS keyword retrieval and semantic vector retrieval "
                    "fused by reciprocal rank"
                ),
                "kg_hybrid": (
                    "Deterministic graph retrieval and answer assembly "
                    "with explicit graph paths"
                ),
                "same_questions": True,
                "path_metric_scope": (
                    "questions with expected_path_evidence_ids"
                ),
                "no_evidence_metric": "refusal_correct",
                "stable_order": {
                    "keyword": "bm25, evidence_id",
                    "semantic": "vector score descending, evidence_id",
                    "fusion": "reciprocal rank descending, evidence_id",
                },
            },
            "limitations": [
                (
                    "Generated relation questions use frozen graph-edge evidence "
                    "as the expected set."
                ),
                (
                    "Manual multi-hop expected evidence is derived from the current "
                    "deterministic engine during question construction."
                ),
                (
                    "Plain RAG has no explicit graph path representation, so path "
                    "metrics are not applicable."
                ),
                (
                    "Questions without expected_path_evidence_ids are excluded from "
                    "the path denominator, including q-070."
                ),
                "No runtime generative model is required for this evaluation.",
            ],
            "results": results,
        }

    def _run_questions(
        self,
        questions: list[EvaluationQuestion],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for question in questions:
            evaluates_path = bool(question.expected_path_evidence_ids)
            plain_start = perf_counter()
            plain_hits = self._plain_rag_hits(question.query)
            plain_elapsed = (perf_counter() - plain_start) * 1000

            hybrid_start = perf_counter()
            answer = self.engine.answer(question.query)
            hybrid_elapsed = (perf_counter() - hybrid_start) * 1000
            hybrid_evidence = [citation.id for citation in answer.citations]

            results.append(
                {
                    "id": question.id,
                    "query": question.query,
                    "expect_no_evidence": question.expect_no_evidence,
                    "expected": question.expected_evidence_ids,
                    "expected_path_evidence_ids": (
                        question.expected_path_evidence_ids
                    ),
                    "plain_rag": self._score(
                        question,
                        plain_hits,
                        plain_elapsed,
                        refused=False,
                        path_evidence=None,
                    ),
                    "kg_hybrid": self._score(
                        question,
                        hybrid_evidence,
                        hybrid_elapsed,
                        refused=answer.sufficiency == EvidenceSufficiency.NONE,
                        path_evidence=list(
                            dict.fromkeys(
                                evidence_id
                                for path in answer.graph_paths
                                for evidence_id in path.evidence_ids
                            )
                        )
                        if evaluates_path
                        else None,
                    ),
                }
            )
        return results

    @contextmanager
    def _stable_retrieval_order(self):
        metadata = self.snapshot.metadata
        original_search_fts = metadata.search_fts
        original_search_phrases = metadata.search_evidence_phrases
        metadata.search_fts = self._stable_search_fts
        metadata.search_evidence_phrases = self._stable_search_evidence_phrases
        try:
            yield
        finally:
            metadata.search_fts = original_search_fts
            metadata.search_evidence_phrases = original_search_phrases

    def _stable_search_fts(
        self,
        query: str,
        limit: int = 10,
        source_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        terms = [term for term in tokenize(query).split() if term]
        if not terms:
            return []
        match_query = " OR ".join(
            f'"{term.replace(chr(34), "")}"'
            for term in terms
        )
        source_clause = ""
        parameters: list[Any] = [match_query]
        if source_types:
            placeholders = ",".join("?" for _ in source_types)
            source_clause = f"AND e.source_type IN ({placeholders})"
            parameters.extend(sorted(source_types))
        parameters.append(limit)
        with self.snapshot.metadata.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.id, c.document_id, c.source_id, c.text, c.entity_ids_json,
                       c.locator, s.title, s.source_classification,
                       s.data_origin, s.data_owner, s.access_scope, s.is_demo,
                       s.publisher, s.published_at, s.url,
                       e.id AS evidence_id, e.source_type, e.review_status,
                       e.input_status, e.fusion_status, e.evidence_status,
                       e.graph_display_role, e.answer_eligible,
                       e.source_record_id, e.source_version, e.source_locator,
                       e.edge_id, e.metadata_json AS evidence_metadata_json,
                       bm25(chunk_fts) AS rank
                FROM chunk_fts
                JOIN chunks c ON c.id = chunk_fts.chunk_id
                JOIN sources s ON s.id = c.source_id
                LEFT JOIN evidence e ON e.chunk_id = c.id
                WHERE chunk_fts MATCH ?
                {source_clause}
                ORDER BY bm25(chunk_fts), e.id
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def _stable_search_evidence_phrases(
        self,
        phrases: list[str],
        *,
        limit: int = 100,
        source_types: set[str] | None = None,
    ) -> list[str]:
        phrases = [phrase for phrase in phrases if phrase.strip()]
        if not phrases:
            return []
        phrase_clause = " OR ".join("c.text LIKE ?" for _ in phrases)
        source_clause = ""
        parameters: list[Any] = [f"%{phrase}%" for phrase in phrases]
        if source_types:
            placeholders = ",".join("?" for _ in source_types)
            source_clause = f"AND e.source_type IN ({placeholders})"
            parameters.extend(sorted(source_types))
        parameters.append(limit)
        with self.snapshot.metadata.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.id
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                WHERE ({phrase_clause})
                  AND e.answer_eligible = 1
                  {source_clause}
                ORDER BY e.id
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def _plain_rag_hits(self, query: str) -> list[str]:
        expanded = self.engine._expanded_text_query(query) or query
        keyword_ids = self._keyword_hits(expanded, limit=20)
        vector_ids = self._vector_hits(query)
        scores: dict[str, float] = {}
        for rank, evidence_id in enumerate(dict.fromkeys(keyword_ids)):
            scores[evidence_id] = scores.get(evidence_id, 0.0) + 1.0 / (60 + rank)
        for rank, evidence_id in enumerate(dict.fromkeys(vector_ids)):
            scores[evidence_id] = scores.get(evidence_id, 0.0) + 1.0 / (60 + rank)
        return [
            evidence_id
            for evidence_id, _score in sorted(
                scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    def _keyword_hits(self, query: str, limit: int = 20) -> list[str]:
        terms = [term for term in tokenize(query).split() if term]
        if not terms:
            return []
        match_query = " OR ".join(
            f'"{term.replace(chr(34), "")}"'
            for term in terms
        )
        with self.snapshot.metadata.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.id AS evidence_id
                FROM chunk_fts
                JOIN chunks c ON c.id = chunk_fts.chunk_id
                JOIN evidence e ON e.chunk_id = c.id
                WHERE chunk_fts MATCH ?
                ORDER BY bm25(chunk_fts), e.id
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall()
        return [str(row["evidence_id"]) for row in rows]

    def _vector_hits(self, query: str) -> list[str]:
        hits = self.snapshot.vectors.search(query, limit=10)
        ranked: list[tuple[float, str]] = []
        for hit in hits:
            chunk = self.snapshot.metadata.get_chunk(hit["chunk_id"])
            if not chunk:
                continue
            with self.snapshot.metadata.connect() as connection:
                rows = connection.execute(
                    "SELECT id FROM evidence WHERE chunk_id = ?",
                    (chunk["id"],),
                ).fetchall()
            ranked.extend(
                (float(hit["score"]), str(row["id"]))
                for row in rows
            )
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return list(dict.fromkeys(evidence_id for _, evidence_id in ranked))

    @staticmethod
    def _score(
        question: EvaluationQuestion,
        retrieved: list[str],
        elapsed_ms: float,
        refused: bool,
        path_evidence: list[str] | None,
    ) -> dict[str, Any]:
        expected = set(question.expected_evidence_ids)
        expected_paths = set(question.expected_path_evidence_ids)
        retrieved_unique = list(dict.fromkeys(retrieved))
        if question.expect_no_evidence:
            return {
                "recall_at_5": None,
                "mrr_at_10": None,
                "ndcg_at_10": None,
                "citation_accuracy": None,
                "path_hit_rate": None,
                "refusal_correct": 1.0 if refused else 0.0,
                "elapsed_ms": elapsed_ms,
                "returned": len(retrieved_unique),
            }
        top5 = retrieved_unique[:5]
        top10 = retrieved_unique[:10]
        recall = len(expected.intersection(top5)) / len(expected) if expected else 0.0
        reciprocal_rank = 0.0
        for index, evidence_id in enumerate(top10, start=1):
            if evidence_id in expected:
                reciprocal_rank = 1.0 / index
                break
        dcg = sum(
            1.0 / math.log2(index + 1)
            for index, evidence_id in enumerate(top10, start=1)
            if evidence_id in expected
        )
        ideal = sum(
            1.0 / math.log2(index + 1)
            for index in range(1, min(len(expected), 10) + 1)
        )
        ndcg = dcg / ideal if ideal else 0.0
        citation_accuracy = (
            len(expected.intersection(top10)) / len(top10) if top10 else 0.0
        )
        path_hit_rate = (
            1.0 if expected_paths.intersection(path_evidence) else 0.0
        ) if path_evidence is not None else None
        return {
            "recall_at_5": recall,
            "mrr_at_10": reciprocal_rank,
            "ndcg_at_10": ndcg,
            "citation_accuracy": citation_accuracy,
            "path_hit_rate": path_hit_rate,
            "refusal_correct": None,
            "elapsed_ms": elapsed_ms,
            "returned": len(retrieved_unique),
        }

    @staticmethod
    def _aggregate(items: list[dict[str, Any]]) -> dict[str, float | int | None]:
        latencies = sorted(float(item["elapsed_ms"]) for item in items)
        p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)

        def mean_metric(key: str) -> tuple[float | None, int]:
            values = [
                float(item[key])
                for item in items
                if item.get(key) is not None
            ]
            return (
                statistics.fmean(values) if values else None,
                len(values),
            )

        recall, retrieval_count = mean_metric("recall_at_5")
        mrr, _ = mean_metric("mrr_at_10")
        ndcg, _ = mean_metric("ndcg_at_10")
        citation_accuracy, _ = mean_metric("citation_accuracy")
        path_hit_rate, path_count = mean_metric("path_hit_rate")
        return {
            "recall_at_5": recall,
            "mrr_at_10": mrr,
            "ndcg_at_10": ndcg,
            "citation_accuracy": citation_accuracy,
            "path_hit_rate": path_hit_rate,
            "retrieval_evaluable_count": retrieval_count,
            "path_evaluable_count": path_count,
            "p95_ms": latencies[p95_index] if latencies else 0.0,
        }
