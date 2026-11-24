from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Iterable
from typing import Any

from app.config import Settings
from app.schemas import (
    Answer,
    Claim,
    ClaimType,
    EvidenceSufficiency,
    GenerationInfo,
    GenerationStatus,
    QAMode,
)
from app.services.qa import (
    GraphAnswerEngine,
    build_evidence_comparisons,
)
from app.services.research import ResearchService
from app.services.runtime_llm import (
    DraftAnswer,
    ParsedQuestion,
    RuntimeLLMClient,
    RuntimeLLMError,
)
from app.services.snapshot import SnapshotContext

EXTERNAL_SOURCE_TYPES = {"literature", "structured", "public", "synthetic", "legacy", ""}
ALLOWED_INTENTS = {
    "negative_evidence",
    "comparison",
    "food_sources",
    "drug_interactions",
    "deficiency",
    "mechanism",
    "functions",
    "lab_tests",
    "recommendations",
    "research",
    "definition",
    "interaction",
    "longitudinal",
    "postprandial",
    "dose_response",
    "exploratory",
    "general",
}
ALLOWED_FILTER_KEYS = {
    "collection",
    "test_family",
    "outcome",
    "evidence_level",
    "result_status",
    "review_status",
}
CAUSAL_MARKERS = {
    "导致",
    "引起",
    "降低",
    "升高",
    "提高",
    "改善",
    "预防",
    "治疗",
    "减少",
    "增加",
}
UNSUPPORTED_STRONG_MARKERS = {
    "已被证明",
    "确切有效",
    "一定有效",
    "保证有效",
    "治愈",
    "替代药物",
}


class RuntimeQAService:
    def __init__(
        self,
        settings: Settings,
        snapshot: SnapshotContext,
        *,
        llm: RuntimeLLMClient | None = None,
    ):
        self.settings = settings
        self.snapshot = snapshot
        self.llm = llm or RuntimeLLMClient(settings)
        self.engine = GraphAnswerEngine(settings, snapshot)
        self.research = ResearchService(settings, snapshot)

    def answer(
        self,
        query: str,
        *,
        session_id: str | None,
        mode: QAMode,
        filters: dict[str, Any] | None = None,
        include_internal_context: bool = False,
        persist: bool = True,
    ) -> Answer:
        started = time.perf_counter()
        explicit_filters = {
            key: value
            for key, value in (filters or {}).items()
            if key in ALLOWED_FILTER_KEYS and str(value).strip()
        }
        safety = self.engine._safety_check(query)
        protected_evidence_allowed = bool(
            self.llm.available
            and getattr(self.llm, "protected_evidence_allowed", False)
        )
        model_mode_allowed = (
            mode == QAMode.DOMAIN or protected_evidence_allowed
        )
        parsed = None
        if self.llm.available and not safety and model_mode_allowed:
            parsed = self._parse(query, mode, explicit_filters)
        effective_filters = {
            **({} if parsed is None else self._validated_filters(parsed.filters)),
            **explicit_filters,
        }
        parsed_entities = (
            self._resolve_entities(parsed.entities)
            if parsed and not parsed.requires_clarification
            else []
        )
        parsed_intent = (
            parsed.intent
            if parsed
            and parsed.confidence >= 0.55
            and parsed.intent in ALLOWED_INTENTS
            else None
        )

        if mode == QAMode.RESEARCH:
            answer = self.research.answer(
                query,
                session_id=session_id,
                filters=effective_filters,
                persist=False,
                entity_names=[node.name for node in parsed_entities],
            )
        else:
            domain = self.engine.answer(
                query,
                session_id,
                source_types=EXTERNAL_SOURCE_TYPES,
                parsed_entities=parsed_entities,
                parsed_intent=parsed_intent,
                include_internal_context=include_internal_context,
                persist=False,
            )
            domain.mode = QAMode.DOMAIN
            domain.data_scope = [
                "external",
                *(
                    ["internal"]
                    if any(
                        citation.data_origin == "internal"
                        for citation in domain.citations
                    )
                    else []
                ),
            ]
            answer = domain
            if mode == QAMode.COMPARISON and not domain.safety_notice:
                internal = self.research.answer(
                    query,
                    session_id=domain.session_id,
                    filters=effective_filters,
                    persist=False,
                    entity_names=[node.name for node in parsed_entities],
                )
                answer = self._combine_comparison(domain, internal)

        answer.applied_filters = effective_filters
        answer.mode = mode
        answer.generation = self._initial_generation(
            parsed_used=bool(parsed_intent or parsed_entities),
        )
        protected_answer = any(
            citation.data_origin == "internal" for citation in answer.citations
        )
        llm_answer_allowed = model_mode_allowed and (
            protected_evidence_allowed or not protected_answer
        )
        if (
            answer.claims
            and not answer.safety_notice
            and self.llm.available
            and llm_answer_allowed
        ):
            answer = self._enhance_with_llm(query, answer, started)
        elif self.llm.available:
            if answer.safety_notice:
                answer.generation.fallback_reason = "safety rule handled the question"
            elif protected_answer and not protected_evidence_allowed:
                answer.generation.fallback_reason = (
                    "internal evidence was not sent to a public-only runtime model"
                )
            elif not model_mode_allowed:
                answer.generation.fallback_reason = (
                    "configured runtime model is public-only; "
                    "research and comparison evidence were not sent"
                )
            else:
                answer.generation.fallback_reason = (
                    "deterministic retrieval produced no claim to rewrite"
                )
            answer.generation.status = GenerationStatus.NOT_ATTEMPTED

        answer.elapsed_ms = int((time.perf_counter() - started) * 1000)
        if persist:
            self._persist(answer)
        return answer

    def _parse(
        self,
        query: str,
        mode: QAMode,
        filters: dict[str, Any],
    ) -> ParsedQuestion | None:
        candidates: dict[str, dict[str, str]] = {}
        for node in [
            *self.engine._link_entities(query),
            *self.snapshot.graph.search_nodes(query, limit=20),
        ]:
            candidates[node.id] = {
                "name": node.name,
                "id": node.id,
                "aliases": " / ".join(node.aliases[:6]),
                "type": node.type,
            }
        try:
            parsed = self.llm.parse_question(
                query,
                mode=mode.value,
                candidate_entities=list(candidates.values()),
                filters=filters,
            )
        except RuntimeLLMError:
            return None
        if parsed is None:
            return None
        parsed.intent = parsed.intent.strip()
        parsed.entities = [
            entity.strip() for entity in parsed.entities[:6] if entity.strip()
        ]
        parsed.confidence = max(0.0, min(float(parsed.confidence), 1.0))
        return parsed

    def _resolve_entities(self, names: Iterable[str]):
        output = []
        seen = set()
        for name in names:
            matches = self.snapshot.graph.search_nodes(name, limit=8)
            if not matches:
                continue
            normalized = GraphAnswerEngine.normalize(name)
            exact = [
                node
                for node in matches
                if normalized
                in {
                    GraphAnswerEngine.normalize(value)
                    for value in [node.name, node.id, *node.aliases]
                }
            ]
            selected = sorted(
                exact or matches,
                key=lambda node: (
                    0 if node.id.startswith("ENT_") else 1,
                    node.id,
                ),
            )[0]
            if selected.id not in seen:
                seen.add(selected.id)
                output.append(selected)
        return output[:4]

    @staticmethod
    def _validated_filters(filters: dict[str, str]) -> dict[str, str]:
        output = {}
        for key, value in filters.items():
            if key not in ALLOWED_FILTER_KEYS:
                continue
            text = str(value).strip()
            if text and len(text) <= 120:
                output[key] = text
        return output

    def _initial_generation(self, *, parsed_used: bool) -> GenerationInfo:
        return GenerationInfo(
            status=(
                GenerationStatus.NOT_ATTEMPTED
                if self.llm.available
                else GenerationStatus.DISABLED
            ),
            configured=self.llm.available,
            provider=self.llm.provider if self.llm.available else "",
            model=self.llm.model if self.llm.available else "",
            semantic_parse_used=parsed_used,
            fallback_reason="" if self.llm.available else "runtime LLM disabled",
            endpoint_class=(
                str(getattr(self.llm, "endpoint_class", ""))
                if self.llm.available
                else ""
            ),
            evidence_policy=(
                str(getattr(self.llm, "evidence_policy", "public_only"))
                if self.llm.available
                else "public_only"
            ),
            protected_evidence_allowed=bool(
                getattr(self.llm, "protected_evidence_allowed", False)
            ),
        )

    def _enhance_with_llm(
        self,
        query: str,
        answer: Answer,
        request_started: float,
    ) -> Answer:
        started = time.perf_counter()
        evidence_payload = self._evidence_payload(answer)
        deterministic = {
            "answer_text": answer.answer_text,
            "intent": answer.intent,
            "claims": [claim.model_dump(mode="json") for claim in answer.claims],
        }
        try:
            draft = self.llm.generate_answer(
                query=query,
                mode=answer.mode.value,
                deterministic_answer=deterministic,
                evidence=evidence_payload,
            )
        except RuntimeLLMError as error:
            answer.generation.status = GenerationStatus.FALLBACK
            answer.generation.fallback_reason = str(error)
            answer.generation.verification = "request_failed"
            answer.generation.latency_ms = int(
                (time.perf_counter() - started) * 1000
            )
            return answer
        errors, generated_claims = self._validate_draft(answer, draft)
        if errors or not generated_claims:
            answer.generation.status = GenerationStatus.FALLBACK
            answer.generation.fallback_reason = "; ".join(errors[:4])
            answer.generation.verification = "failed"
            answer.generation.rejected_claim_count = len(
                draft.claims if draft else []
            )
            answer.generation.latency_ms = int(
                (time.perf_counter() - started) * 1000
            )
            return answer

        opening = self._clean_narrative(draft.opening if draft else "")
        closing = self._clean_narrative(draft.closing if draft else "")
        sections = [
            section
            for section in [
                opening,
                *(claim.text for claim in generated_claims),
                closing,
            ]
            if section
        ]
        answer.answer_text = "\n\n".join(sections)
        answer.claims = generated_claims
        answer.comparisons = build_evidence_comparisons(
            answer.claims,
            answer.citations,
        )
        answer.generation.status = GenerationStatus.GENERATED
        answer.generation.used = True
        answer.generation.accepted_claim_count = len(generated_claims)
        answer.generation.verification = "passed"
        answer.generation.latency_ms = int(
            (time.perf_counter() - started) * 1000
        )
        return answer

    def _validate_draft(
        self,
        answer: Answer,
        draft: DraftAnswer | None,
    ) -> tuple[list[str], list[Claim]]:
        if draft is None:
            return ["model did not return a valid JSON answer"], []
        if not draft.claims:
            return ["model returned no evidence-bound claims"], []
        errors: list[str] = []
        citations = {citation.id: citation for citation in answer.citations}
        base_by_id = {
            evidence_id: claim
            for claim in answer.claims
            for evidence_id in claim.evidence_ids
        }
        evidence_text = {
            citation.id: " ".join(
                [
                    base_by_id[citation.id].text if citation.id in base_by_id else "",
                    citation.snippet,
                    citation.analysis_context,
                    citation.effect_size,
                    citation.p_value,
                    citation.q_value,
                    citation.sample_n,
                    citation.model_type,
                    citation.test_family,
                ]
            )
            for citation in answer.citations
        }
        output: list[Claim] = []
        covered: set[str] = set()
        for index, item in enumerate(draft.claims, start=1):
            text = self._clean_claim(item.text)
            evidence_ids = list(dict.fromkeys(item.evidence_ids))
            if not text:
                errors.append(f"claim {index} is empty")
                continue
            if not evidence_ids or any(
                evidence_id not in citations for evidence_id in evidence_ids
            ):
                errors.append(f"claim {index} cites unknown evidence")
                continue
            support_text = " ".join(evidence_text[item_id] for item_id in evidence_ids)
            if self._new_numbers(text, support_text):
                errors.append(f"claim {index} introduces an unsupported number")
            if self._unsupported_causal_language(text, support_text):
                errors.append(f"claim {index} overstates causality")
            if self._unsupported_terms(text, support_text):
                errors.append(f"claim {index} is not sufficiently supported by text")
            base_claims = [base_by_id[item_id] for item_id in evidence_ids if item_id in base_by_id]
            if not base_claims:
                errors.append(f"claim {index} has no deterministic grounding")
                continue
            claim_types = {claim.claim_type for claim in base_claims}
            claim_type = (
                next(iter(claim_types))
                if len(claim_types) == 1
                else ClaimType.CONFLICT
            )
            relation = base_claims[0].relation
            boundary = base_claims[0].boundary_note
            if len(base_claims) > 1:
                boundary = (
                    "该结论综合了多项证据，应结合各自研究条件、"
                    "统计结果和适用边界阅读。"
                )
            output.append(
                Claim(
                    id=f"llm-claim-{uuid.uuid4().hex[:10]}",
                    text=text,
                    evidence_ids=evidence_ids,
                    relation=relation,
                    claim_type=claim_type,
                    boundary_note=boundary,
                )
            )
            covered.update(evidence_ids)
        critical = {
            evidence_id
            for claim in answer.claims
            if claim.claim_type in {ClaimType.NEGATIVE, ClaimType.CONFLICT}
            for evidence_id in claim.evidence_ids
        }
        if critical - covered:
            errors.append("important negative or conflicting evidence was omitted")
        required_coverage = min(len(citations), max(1, int(len(citations) * 0.75)))
        if len(covered) < required_coverage:
            errors.append("generated answer does not cover enough source evidence")
        return errors, output

    @staticmethod
    def _clean_claim(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()[:700]

    @staticmethod
    def _clean_narrative(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        if not cleaned or re.search(r"\d", cleaned):
            return ""
        if any(marker in cleaned for marker in UNSUPPORTED_STRONG_MARKERS):
            return ""
        if any(marker in cleaned for marker in CAUSAL_MARKERS):
            return ""
        return cleaned[:280]

    @staticmethod
    def _new_numbers(text: str, source_text: str) -> bool:
        for number in re.findall(r"\d+(?:\.\d+)?%?", text):
            if number not in source_text:
                return True
        return False

    @staticmethod
    def _unsupported_causal_language(text: str, source_text: str) -> bool:
        for marker in CAUSAL_MARKERS:
            if marker in text and marker not in source_text:
                return True
        return False

    @staticmethod
    def _unsupported_terms(text: str, source_text: str) -> bool:
        if any(marker in text for marker in UNSUPPORTED_STRONG_MARKERS):
            return True
        latin_terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,}", text)
        }
        if latin_terms and not any(term in source_text.lower() for term in latin_terms):
            return True
        cjk = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if len(cjk) >= 8:
            bigrams = {cjk[index : index + 2] for index in range(len(cjk) - 1)}
            matches = sum(1 for item in bigrams if item in source_text)
            if matches < max(2, int(len(bigrams) * 0.08)):
                return True
        return False

    def _evidence_payload(self, answer: Answer) -> list[dict[str, Any]]:
        payload = []
        used_chars = 0
        for citation in answer.citations:
            item = {
                "id": citation.id,
                "source_type": citation.source_type,
                "data_origin": citation.data_origin.value,
                "access_scope": citation.access_scope.value,
                "title": citation.source_title,
                "snippet": citation.snippet[:1600],
                "analysis_context": citation.analysis_context,
                "test_family": citation.test_family,
                "effect_size": citation.effect_size,
                "p_value": citation.p_value,
                "q_value": citation.q_value,
                "sample_n": citation.sample_n,
                "model_type": citation.model_type,
                "review_status": citation.review_status,
                "conflict_id": citation.conflict_id,
            }
            size = len(json.dumps(item, ensure_ascii=False))
            if used_chars + size > self.settings.runtime_llm_max_context_chars:
                break
            used_chars += size
            payload.append(item)
        return payload

    def _combine_comparison(self, domain: Answer, internal: Answer) -> Answer:
        if not internal.claims:
            internal.answer_text = (
                "对照模式已分别检索外部与内部证据。当前内部队列没有找到"
                "与问题直接匹配的统计结果；外部证据仍保留在上方回答中。"
            )
        domain.answer_text = (
            "外部证据\n"
            + domain.answer_text
            + "\n\n内部队列证据\n"
            + internal.answer_text
            + "\n\n两类证据按来源并列展示，不自动合并为同一效应或因果关系。"
        )
        domain.claims = domain.claims + internal.claims
        domain.citations = domain.citations + internal.citations
        domain.comparisons = build_evidence_comparisons(
            domain.claims,
            domain.citations,
        )
        domain.mode = QAMode.COMPARISON
        domain.data_scope = ["external", "internal"]
        if domain.sufficiency == EvidenceSufficiency.NONE:
            domain.sufficiency = internal.sufficiency
        elif internal.sufficiency == EvidenceSufficiency.SUFFICIENT:
            domain.sufficiency = EvidenceSufficiency.SUFFICIENT
        return domain

    def _persist(self, answer: Answer) -> None:
        metadata = self.snapshot.metadata
        metadata.create_session(answer.session_id, self.settings.session_ttl_hours)
        metadata.add_message(
            answer.session_id,
            "user",
            answer.query,
            {
                "mode": answer.mode.value,
                "filters": answer.applied_filters,
            },
        )
        metadata.add_message(
            answer.session_id,
            "assistant",
            answer.answer_text,
            {
                "mode": answer.mode.value,
                "intent": answer.intent,
                "data_scope": answer.data_scope,
                "evidence_ids": [citation.id for citation in answer.citations],
                "generation": answer.generation.model_dump(mode="json"),
            },
        )
        metadata.log_query(
            answer.session_id,
            answer.query,
            f"{answer.mode.value}:{answer.intent}",
            answer.sufficiency.value,
            answer.elapsed_ms,
            answer.data_version.version,
        )
