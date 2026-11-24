from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter
from typing import Any

from app.config import Settings
from app.schemas import (
    Answer,
    Citation,
    Claim,
    EvidenceSufficiency,
    QAMode,
    ResearchDistributionItem,
    ResearchEffectPoint,
    ResearchEffectSeries,
    ResearchEvidenceResponse,
    ResearchFacetOption,
    ResearchFacets,
    ResearchInsights,
    ResearchOverview,
    SearchResult,
)
from app.services.qa import (
    build_evidence_comparisons,
    claim_science_profile,
    natural_evidence_sentence,
)
from app.services.snapshot import SnapshotContext
from app.storage.database import tokenize

CONTEXTUAL_FAMILIES = {
    "postprandial",
    "vk_vd_interaction",
    "sex_interaction",
    "obesity_interaction",
    "reverse_causality",
    "dose_response",
    "mediation",
}
FAMILY_LABELS = {
    "cross_sectional": "基线横断面",
    "longitudinal": "纵向变化",
    "postprandial": "餐后动力学",
    "vk_vd_interaction": "维生素K×维生素D交互",
    "sex_interaction": "性别交互",
    "obesity_interaction": "肥胖状态交互",
    "reverse_causality": "反向因果探索",
    "dose_response": "剂量反应",
    "mediation": "中介分析",
}
RESULT_LABELS = {
    "positive_association": "正向关联",
    "positive_longitudinal": "纵向变化",
    "positive_kinetics": "餐后动力学",
    "positive_interaction": "交互作用",
    "trend_interaction": "交互趋势",
    "positive_dose_response": "剂量反应",
    "negative": "阴性结果",
    "negative_mechanism": "机制阴性",
    "model_inconsistent": "模型不一致",
    "exploratory_reverse": "反向探索",
    "candidate": "候选证据",
}
RESEARCH_SAFETY_MARKERS = {
    "开多少药",
    "服用剂量",
    "停药",
    "换药",
    "怎么治疗",
    "确诊",
    "急诊",
    "胸痛",
}
MATCH_STATUS_LABELS = {
    "consistent_validated": "研究结果一致",
    "direction_conflict": "关联方向存在差异",
    "significance_conflict": "统计结果存在差异",
    "compatible_contextual_evidence": "相关科学证据",
    "endpoint_mismatch": "研究条件存在差异",
    "internal_unique_evidence": "本课题发现 · 尚未匹配外部证据",
    "unclassified": "待匹配审核",
}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("metadata_json")
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _is_core(row: dict[str, Any]) -> bool:
    return bool(row.get("core_48_flag")) or str(
        _metadata(row).get("core_48_flag", "")
    ).lower() in {"true", "1"}


def _family(row: dict[str, Any]) -> str:
    return str(row.get("test_family") or _metadata(row).get("test_family") or "")


def _value(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) if row.get(key) not in (None, "") else _metadata(row).get(key) or "")


def _label(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value or "未分类")


def _facet_options(values: list[str], labels: dict[str, str] | None = None) -> list[ResearchFacetOption]:
    counts = Counter(value for value in values if value)
    return [
        ResearchFacetOption(
            value=value,
            label=(labels or {}).get(value, value),
            count=count,
        )
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _distribution(
    values: list[str],
    labels: dict[str, str] | None = None,
    *,
    denominator: int | None = None,
) -> list[ResearchDistributionItem]:
    counts = Counter(value for value in values if value)
    total = denominator if denominator is not None else sum(counts.values())
    return [
        ResearchDistributionItem(
            key=value,
            label=(labels or {}).get(value, value),
            count=count,
            percentage=round(count / total * 100, 1) if total else 0.0,
        )
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


class ResearchService:
    def __init__(self, settings: Settings, snapshot: SnapshotContext):
        self.settings = settings
        self.snapshot = snapshot
        self.metadata = snapshot.metadata

    def overview(self) -> ResearchOverview:
        rows = self.metadata.all_internal_evidence()
        core = [row for row in rows if _is_core(row)]
        contextual = [row for row in rows if _family(row) in CONTEXTUAL_FAMILIES]
        overlap = [
            row
            for row in rows
            if _is_core(row) and _family(row) in CONTEXTUAL_FAMILIES
        ]
        return ResearchOverview(
            data_version=self.snapshot.version,
            total_internal_records=len(rows),
            core_records=len(core),
            contextual_records=len(contextual),
            core_contextual_overlap=len(overlap),
            source_count=len({row["source_id"] for row in rows}),
            grade_distribution=dict(
                Counter(str(row.get("evidence_level") or "") for row in rows)
            ),
            result_distribution=dict(
                Counter(str(row.get("evidence_status") or "") for row in rows)
            ),
            test_family_distribution=dict(
                Counter(_family(row) for row in rows if _family(row))
            ),
            cohort_description="中国高代谢风险成人 6 个月生活方式干预队列",
        )

    def facets(self) -> ResearchFacets:
        rows = self.metadata.all_internal_evidence()
        outcomes = {
            str(metadata.get("object_label") or "")
            for row in rows
            if (metadata := _metadata(row))
        } - {""}
        return ResearchFacets(
            test_families=_facet_options(
                [_family(row) for row in rows],
                FAMILY_LABELS,
            ),
            evidence_levels=_facet_options(
                [str(row.get("evidence_level") or "") for row in rows]
            ),
            result_statuses=_facet_options(
                [str(row.get("evidence_status") or "") for row in rows],
                RESULT_LABELS,
            ),
            review_statuses=_facet_options(
                [str(row.get("review_status") or "") for row in rows]
            ),
            outcomes=_facet_options(sorted(outcomes)),
        )

    def insights(self) -> ResearchInsights:
        rows = self.metadata.all_internal_evidence()
        total = len(rows)
        match_values: list[str] = []
        governance_values: list[str] = []
        status_values: list[str] = []
        grade_values: list[str] = []
        match_status_available = False
        effect_groups: dict[
            tuple[str, str, str, str],
            list[ResearchEffectPoint],
        ] = {}

        for row in rows:
            metadata = _metadata(row)
            match_status = str(
                row.get("matching_status")
                or row.get("match_status")
                or metadata.get("matching_status")
                or metadata.get("match_status")
                or ""
            )
            if match_status:
                match_status_available = True
            match_values.append(match_status or "unclassified")

            retention = str(
                row.get("retention_status")
                or metadata.get("retention_status")
                or "未标记"
            )
            governance_values.append(retention)
            status_values.append(str(row.get("evidence_status") or "未标记"))
            grade_values.append(str(row.get("evidence_level") or "未标记"))

            effect = _number(row.get("effect_size") or metadata.get("effect_size"))
            if effect is None:
                continue
            outcome = str(metadata.get("object_label") or row.get("object_label") or "未命名结局")
            model_type = str(row.get("model_type") or metadata.get("model_type") or "未报告模型")
            analysis_context = str(
                row.get("analysis_context")
                or metadata.get("analysis_context")
                or "未报告分析条件"
            )
            exposure = str(metadata.get("subject_label") or row.get("subject_label") or "未命名暴露")
            ci_low = _number(row.get("ci_low") or metadata.get("ci_low"))
            ci_high = _number(row.get("ci_high") or metadata.get("ci_high"))
            if ci_low is None or ci_high is None:
                ci_low = None
                ci_high = None
            key = (model_type, outcome, analysis_context, str(metadata.get("effect_unit") or ""))
            effect_groups.setdefault(key, []).append(
                ResearchEffectPoint(
                    evidence_id=str(row.get("id") or ""),
                    label=exposure,
                    value=effect,
                    ci_low=ci_low,
                    ci_high=ci_high,
                    result_status=str(row.get("evidence_status") or "未标记"),
                    evidence_level=str(row.get("evidence_level") or "未标记"),
                )
            )

        series = []
        for (model_type, outcome, context, unit), points in effect_groups.items():
            if len(points) < 2:
                continue
            series.append(
                ResearchEffectSeries(
                    id=f"{outcome}:{model_type}:{context}",
                    title=f"{outcome} · {model_type}",
                    outcome=outcome,
                    model_type=model_type,
                    analysis_context=context,
                    unit=unit or "未报告单位",
                    reference_value=0,
                    points=points,
                )
            )
        series.sort(key=lambda item: (-len(item.points), item.title))

        limitations = []
        if not match_status_available:
            limitations.append(
                "当前冻结内部证据表没有审核匹配状态字段，因此不会把保留状态推断为科学冲突。"
            )
        if not any(point.ci_low is not None for item in series for point in item.points):
            limitations.append(
                "当前可用于作图的效应量没有真实 CI，图件只显示点估计，不能绘制置信区间。"
            )
        if any(item.unit == "未报告单位" for item in series):
            limitations.append(
                "部分效应量未提供单位或标准化口径，图注保留“未报告单位”，不推断可合并性。"
            )

        return ResearchInsights(
            data_version=self.snapshot.version,
            total_records=total,
            match_status_available=match_status_available,
            match_note=(
                "按已审核的内外部匹配字段汇总。"
                if match_status_available
                else "审核匹配表尚未接入；矩阵不把 retention_status 或显著性差异等同医学冲突。"
            ),
            match_categories=_distribution(
                match_values,
                MATCH_STATUS_LABELS,
                denominator=total,
            ),
            governance_categories=_distribution(governance_values),
            status_distribution=_distribution(status_values, RESULT_LABELS, denominator=total),
            grade_distribution=_distribution(grade_values, denominator=total),
            effect_series=series[:24],
            limitations=limitations,
        )

    def search(
        self,
        *,
        query: str = "",
        collection: str = "all",
        test_family: str = "",
        outcome: str = "",
        evidence_level: str = "",
        result_status: str = "",
        review_status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> ResearchEvidenceResponse:
        filters = {
            "collection": collection,
            "test_family": test_family,
            "outcome": outcome,
            "evidence_level": evidence_level,
            "result_status": result_status,
            "review_status": review_status,
            "query": query,
        }
        rows = [
            row
            for row in self.metadata.all_internal_evidence()
            if self._matches_filters(row, **filters)
        ]
        rows.sort(
            key=lambda row: (
                -self._relevance(row, query),
                -int(_is_core(row)),
                str(row.get("id") or ""),
            )
        )
        total = len(rows)
        start = max(0, page - 1) * page_size
        selected = rows[start : start + page_size]
        return ResearchEvidenceResponse(
            items=[self._search_result(row, query) for row in selected],
            total=total,
            page=page,
            page_size=page_size,
            facets=self.facets(),
            applied_filters={
                key: value for key, value in filters.items() if value not in {"", None}
            },
        )

    def answer(
        self,
        query: str,
        *,
        session_id: str | None = None,
        filters: dict[str, Any] | None = None,
        persist: bool = True,
        entity_names: list[str] | None = None,
    ) -> Answer:
        started = time.perf_counter()
        normalized = re.sub(r"\s+", "", query.lower())
        compact = re.sub(r"\s+", "", query)
        if persist:
            session_id = self.metadata.create_session(
                session_id if self.metadata.session_exists(session_id or "") else None,
                self.settings.session_ttl_hours,
            )
            self.metadata.add_message(session_id, "user", query)
        else:
            session_id = session_id or str(uuid.uuid4())

        if any(marker in compact for marker in RESEARCH_SAFETY_MARKERS):
            notice = (
                "研究模式只展示队列统计证据，不提供个体诊断、处方、停药或换药决定。"
                "请由医生或药师结合完整临床信息评估。"
            )
            answer = Answer(
                session_id=session_id,
                query=query,
                normalized_query=normalized,
                intent="medical_safety",
                answer_text=notice,
                sufficiency=EvidenceSufficiency.NONE,
                safety_notice=notice,
                data_version=self.snapshot.data_version,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                mode=QAMode.RESEARCH,
                data_scope=["internal"],
            )
            if persist:
                self._persist(answer)
            return answer

        applied = dict(filters or {})
        rows = [
            row
            for row in self.metadata.all_internal_evidence()
            if self._matches_filters(
                row,
                collection=str(applied.get("collection") or "all"),
                test_family=str(applied.get("test_family") or ""),
                outcome=str(applied.get("outcome") or ""),
                evidence_level=str(applied.get("evidence_level") or ""),
                result_status=str(applied.get("result_status") or ""),
                review_status=str(applied.get("review_status") or ""),
                query="",
            )
        ]
        semantic_entities = [
            re.sub(r"\s+", "", name.lower())
            for name in entity_names or []
            if name.strip()
        ]
        ranked = sorted(
            (
                (
                    self._relevance(row, query)
                    + self._entity_relevance(row, semantic_entities),
                    row,
                )
                for row in rows
            ),
            key=lambda item: (-item[0], str(item[1].get("id") or "")),
        )
        relevant = [row for score, row in ranked if score > 0]
        if not relevant and self._looks_like_evidence_request(query):
            relevant = [row for _, row in ranked[:5]]
        selected = relevant[:8]
        if not selected:
            text = (
                "当前内部队列证据中没有找到与这个问题直接匹配的统计结果。"
                "研究模式不会用外部文献替代内部证据，也不会把无匹配解释为阴性结论。"
            )
            answer = Answer(
                session_id=session_id,
                query=query,
                normalized_query=normalized,
                intent="no_evidence",
                answer_text=text,
                sufficiency=EvidenceSufficiency.NONE,
                data_version=self.snapshot.data_version,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                mode=QAMode.RESEARCH,
                data_scope=["internal"],
                applied_filters=applied,
            )
            if persist:
                self._persist(answer)
            return answer

        claims = [self._claim(row) for row in selected]
        citations = [self._citation(row) for row in selected]
        result_statuses = {str(row.get("evidence_status") or "") for row in selected}
        intent = self._intent(result_statuses, query)
        caution = ""
        if "negative" in result_statuses or any(
            status.startswith("negative") for status in result_statuses
        ):
            caution = (
                "\n\n阴性结果表示当前模型未观察到显著关系，"
                "不能据此证明该关系不存在或证明干预无效。"
            )
        if any(status in {"model_inconsistent", "exploratory_reverse"} for status in result_statuses):
            caution += (
                "\n\n模型不一致或反向探索结果属于需要外部验证的探索性发现，"
                "不能据此推断因果方向。"
            )
        answer_text = (
            "从本项目内部队列的统计证据看：\n"
            + "\n".join(f"- {claim.text}" for claim in claims)
            + "\n\n这些结果反映特定分析条件、模型和样本下的统计关联。"
            + "内部证据标记为 internal/private，不进入公开构建。"
            + caution
        )
        answer = Answer(
            session_id=session_id,
            query=query,
            normalized_query=normalized,
            intent=intent,
            answer_text=answer_text,
            claims=claims,
            citations=citations,
            comparisons=build_evidence_comparisons(claims, citations),
            sufficiency=(
                EvidenceSufficiency.SUFFICIENT
                if len(claims) >= 2
                else EvidenceSufficiency.PARTIAL
            ),
            data_version=self.snapshot.data_version,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            mode=QAMode.RESEARCH,
            data_scope=["internal"],
            applied_filters=applied,
        )
        if persist:
            self._persist(answer)
        return answer

    def _persist(self, answer: Answer) -> None:
        self.metadata.add_message(
            answer.session_id,
            "assistant",
            answer.answer_text,
            {
                "mode": answer.mode.value,
                "intent": answer.intent,
                "evidence_ids": [citation.id for citation in answer.citations],
                "data_scope": answer.data_scope,
            },
        )
        self.metadata.log_query(
            answer.session_id,
            answer.query,
            f"{answer.mode.value}:{answer.intent}",
            answer.sufficiency.value,
            answer.elapsed_ms,
            answer.data_version.version,
        )

    def _matches_filters(
        self,
        row: dict[str, Any],
        *,
        collection: str,
        test_family: str,
        outcome: str,
        evidence_level: str,
        result_status: str,
        review_status: str,
        query: str,
    ) -> bool:
        if collection == "core" and not _is_core(row):
            return False
        if collection == "contextual" and _family(row) not in CONTEXTUAL_FAMILIES:
            return False
        if test_family and _family(row) != test_family:
            return False
        metadata = _metadata(row)
        if outcome and outcome.lower() not in {
            str(metadata.get("object_label") or "").lower(),
            str(metadata.get("subject_label") or "").lower(),
        }:
            return False
        if evidence_level and str(row.get("evidence_level") or "") != evidence_level:
            return False
        if result_status and str(row.get("evidence_status") or "") != result_status:
            return False
        if review_status and str(row.get("review_status") or "") != review_status:
            return False
        if query and self._relevance(row, query) <= 0:
            return False
        return True

    @staticmethod
    def _relevance(row: dict[str, Any], query: str) -> int:
        if not query.strip():
            return 1
        metadata = _metadata(row)
        haystack = " ".join(
            [
                str(metadata.get("subject_label") or ""),
                str(metadata.get("predicate") or ""),
                str(metadata.get("object_label") or ""),
                str(metadata.get("analysis_context") or ""),
                str(row.get("evidence_status") or ""),
                _family(row),
                str(row.get("chunk_text") or ""),
            ]
        ).lower()
        terms = [
            term
            for term in tokenize(query).split()
            if len(term) >= 2 and term not in {"什么", "关系", "内部", "队列", "维生素"}
        ]
        normalized = re.sub(r"\s+", "", query.lower())
        score = sum(3 for term in terms if term in haystack)
        for key in ("subject_label", "object_label"):
            label = re.sub(r"\s+", "", str(metadata.get(key) or "").lower())
            if label and label in normalized:
                score += 8
        return score

    @staticmethod
    def _looks_like_evidence_request(query: str) -> bool:
        return any(
            marker in query
            for marker in ("内部", "队列", "证据", "研究", "分析", "VK", "MK", "GLU", "TG")
        )

    @staticmethod
    def _entity_relevance(row: dict[str, Any], entity_names: list[str]) -> int:
        if not entity_names:
            return 0
        metadata = _metadata(row)
        labels = [
            re.sub(r"\s+", "", str(metadata.get(key) or "").lower())
            for key in ("subject_label", "object_label")
        ]
        return sum(
            8
            for entity in entity_names
            if any(entity in label or label in entity for label in labels if label)
        )

    def _claim(self, row: dict[str, Any]) -> Claim:
        metadata = _metadata(row)
        subject = str(metadata.get("subject_label") or "")
        predicate = str(metadata.get("predicate") or "")
        target = str(metadata.get("object_label") or "")
        result_status = str(row.get("evidence_status") or "")
        p_value = _value(row, "p_value")
        non_significant = False
        try:
            non_significant = bool(p_value) and float(p_value) >= 0.05
        except ValueError:
            non_significant = False
        if result_status == "negative" or predicate.startswith("no_"):
            relation_text = (
                f"当前队列分析未观察到{subject}与{target}之间存在显著关系。"
            )
        elif result_status == "candidate" or (
            non_significant and predicate.startswith(("associated", "cross_"))
        ):
            relation_text = (
                f"当前队列记录了{subject}与{target}的关联分析，"
                "但该候选记录未达到显著阈值，不能表述为已确认关联。"
            )
        elif result_status == "model_inconsistent":
            relation_text = (
                f"{subject}与{target}的分析在不同模型中方向或显著性不一致，"
                "应作为模型不一致结果解释。"
            )
        else:
            relation_text = natural_evidence_sentence(subject, predicate, target)
        stats = self._stats_text(row)
        model = _value(row, "model_type")
        context = _value(row, "analysis_context")
        text = relation_text
        if stats:
            text += f"（{stats}"
            if model:
                text += f"；模型：{model}"
            if context:
                text += f"；分析条件：{context}"
            text += "）"
        claim_type, boundary = claim_science_profile(predicate, text)
        return Claim(
            id=f"research-claim-{uuid.uuid4().hex[:10]}",
            text=text,
            evidence_ids=[str(row["id"])],
            relation=predicate,
            claim_type=claim_type,
            boundary_note=boundary,
        )

    def _citation(self, row: dict[str, Any]) -> Citation:
        return Citation(
            id=str(row["id"]),
            source_id=str(row["source_id"]),
            source_title=str(row["title"]),
            source_type=str(row.get("source_table_type") or row.get("source_type") or ""),
            source_classification=str(row.get("source_classification") or ""),
            data_origin="internal",
            data_owner=str(row.get("data_owner") or ""),
            access_scope="private",
            publisher=str(row.get("publisher") or ""),
            published_at=str(row.get("published_at") or ""),
            url=str(row.get("url") or ""),
            evidence_level=str(row.get("evidence_level") or ""),
            locator=str(row.get("locator") or ""),
            snippet=str(row.get("chunk_text") or ""),
            is_demo=bool(row.get("is_demo")),
            review_status=str(row.get("review_status") or ""),
            input_status=str(row.get("input_status") or ""),
            fusion_status=str(row.get("fusion_status") or ""),
            evidence_status=str(row.get("evidence_status") or ""),
            source_version=str(row.get("source_version") or ""),
            source_locator=str(row.get("source_locator") or ""),
            analysis_context=_value(row, "analysis_context"),
            effect_size=_value(row, "effect_size"),
            p_value=_value(row, "p_value"),
            q_value=_value(row, "q_value"),
            sample_n=_value(row, "sample_n"),
            model_type=_value(row, "model_type"),
            test_family=_family(row),
            core_48=_is_core(row),
            retention_status=_value(row, "retention_status"),
            conflict_id=_value(row, "conflict_id"),
        )

    def _search_result(self, row: dict[str, Any], query: str) -> SearchResult:
        metadata = _metadata(row)
        evidence_json = {
            **metadata,
            "evidence_id": row["id"],
            "data_origin": "internal",
            "access_scope": "private",
            "source_title": row.get("title"),
            "source_classification": row.get("source_classification"),
            "source_locator": row.get("source_locator"),
            "snippet": row.get("chunk_text"),
        }
        return SearchResult(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["chunk_id"]),
            source_id=str(row["source_id"]),
            title=str(row["title"]),
            source_classification=str(row.get("source_classification") or ""),
            data_origin="internal",
            data_owner=str(row.get("data_owner") or ""),
            access_scope="private",
            evidence_level=str(row.get("evidence_level") or ""),
            source_type=str(row.get("source_type") or ""),
            review_status=str(row.get("review_status") or ""),
            input_status=str(row.get("input_status") or ""),
            fusion_status=str(row.get("fusion_status") or ""),
            evidence_status=str(row.get("evidence_status") or ""),
            graph_display_role=str(row.get("graph_display_role") or ""),
            answer_eligible=bool(row.get("answer_eligible")),
            source_record_id=str(row.get("source_record_id") or ""),
            source_version=str(row.get("source_version") or ""),
            source_locator=str(row.get("source_locator") or ""),
            url=str(row.get("url") or ""),
            predicate=str(metadata.get("predicate") or ""),
            snippet=str(row.get("chunk_text") or "")[:360],
            entity_ids=json.loads(row.get("entity_ids_json") or "[]"),
            evidence_json=evidence_json,
            score=float(self._relevance(row, query)),
            is_demo=bool(row.get("is_demo")),
            test_family=_family(row),
            analysis_context=_value(row, "analysis_context"),
            effect_size=_value(row, "effect_size"),
            ci_low=_value(row, "ci_low"),
            ci_high=_value(row, "ci_high"),
            p_value=_value(row, "p_value"),
            q_value=_value(row, "q_value"),
            sample_n=_value(row, "sample_n"),
            model_type=_value(row, "model_type"),
            core_48=_is_core(row),
            retention_status=_value(row, "retention_status"),
            conflict_id=_value(row, "conflict_id"),
        )

    @staticmethod
    def _stats_text(row: dict[str, Any]) -> str:
        pieces = []
        if _value(row, "effect_size"):
            pieces.append(f"效应量 {_value(row, 'effect_size')}")
        if _value(row, "ci_low") or _value(row, "ci_high"):
            pieces.append(
                f"95%CI {_value(row, 'ci_low') or 'NA'}–{_value(row, 'ci_high') or 'NA'}"
            )
        if _value(row, "p_value"):
            pieces.append(f"P={_value(row, 'p_value')}")
        if _value(row, "q_value"):
            pieces.append(f"Q={_value(row, 'q_value')}")
        if _value(row, "sample_n"):
            pieces.append(f"n={_value(row, 'sample_n')}")
        return "，".join(pieces)

    @staticmethod
    def _intent(result_statuses: set[str], query: str) -> str:
        if any(status.startswith("negative") for status in result_statuses):
            return "negative_evidence"
        if any("interaction" in status for status in result_statuses):
            return "interaction"
        if any("dose_response" in status for status in result_statuses):
            return "dose_response"
        if any("longitudinal" in status for status in result_statuses):
            return "longitudinal"
        if any("kinetics" in status or "postprandial" in query for status in result_statuses):
            return "postprandial"
        if any("reverse" in status or "inconsistent" in status for status in result_statuses):
            return "exploratory"
        return "research"
