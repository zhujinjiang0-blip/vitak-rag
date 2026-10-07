from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.config import Settings
from app.schemas import (
    Answer,
    Citation,
    Claim,
    EvidenceSufficiency,
    GraphEdge,
    GraphNode,
    GraphPath,
)
from app.services.snapshot import SnapshotContext
from app.storage.database import MetadataStore
from app.storage.graph import KuzuGraphStore
from app.storage.vector import ChromaVectorStore

SAFETY_RULES = [
    (
        {"出血不止", "止不住血", "大量出血", "黑便", "血便", "呕血", "严重头痛", "呼吸困难"},
        "这可能属于需要紧急处理的症状。请立即联系急救服务或尽快前往急诊，不要等待线上问答结果。",
        "emergency",
    ),
    (
        {"给我开药", "怎么停药", "自己停药", "华法林吃多少", "抗凝药剂量", "具体剂量"},
        "涉及处方、停药或剂量调整的问题必须由医生或药师评估。本系统不能提供个体化用药决定。",
        "medication",
    ),
    (
        {"我得了什么病", "帮我诊断", "是否患病", "确诊"},
        "本系统不能进行疾病诊断。请携带症状、检验结果和用药信息咨询专业医疗人员。",
        "diagnosis",
    ),
]


INTENT_RULES: list[tuple[str, set[str]]] = [
    ("comparison", {"区别", "比较", "不同", "差异", "哪个好", "对比"}),
    ("food_sources", {"食物", "吃什么", "来源", "蔬菜", "叶菜", "纳豆", "饮食", "含有", "富含"}),
    ("drug_interactions", {"相互作用", "一起吃", "同服", "药物", "华法林", "抗凝", "抗生素"}),
    ("deficiency", {"缺乏", "不足", "缺什么", "风险人群", "谁会", "症状"}),
    ("functions", {"作用", "功能", "参与", "有什么好处", "影响什么", "机制", "凝血"}),
    ("lab_tests", {"检测", "检查", "化验", "指标", "INR", "PT", "PIVKA", "评估", "测量", "反映"}),
    ("recommendations", {"建议", "推荐", "摄入量", "每天", "孕妇", "新生儿", "老人", "适用", "人群"}),
    ("research", {"研究", "RCT", "证据", "指南", "文献", "临床试验"}),
    ("definition", {"是什么", "什么是", "定义", "介绍", "介绍一下"}),
]


RELATION_TEXT = {
    "IS_FORM_OF": "{source}是{target}的一种形式。",
    "SUPPORTS": "{source}参与或支持{target}。",
    "PARTICIPATES_IN": "{source}参与{target}。",
    "ACTIVATES": "{source}参与{target}的活化或功能调节。",
    "POTENTIALLY_PROTECTS_AGAINST": "知识库记录了{source}与{target}风险之间的关联，但不能据此作出个体医疗结论。",
    "MAY_CONTRIBUTE_TO": "{source}可能对{target}作出贡献，解释时需考虑个体差异。",
    "DISRUPTS": "{source}会干扰{target}。",
    "CAN_CAUSE": "{source}可能导致或促成{target}。",
    "CAN_CONTRIBUTE_TO": "{source}可能促成{target}。",
    "AT_RISK": "{source}属于{target}相关风险需要关注的人群。",
    "INHIBITS": "{source}可抑制{target}。",
    "INCLUDES": "{source}包括{target}。",
    "ASSOCIATED_WITH": "{source}与{target}存在关联，具体临床意义需结合监测与专业评估。",
    "CAN_ALTER": "{source}可能改变{target}。",
    "CONTAINS": "{source}含有{target}。",
    "RICH_IN": "{source}可被视为富含{target}的食物类别之一。",
    "MAY_CONTAIN": "{source}可能含有{target}，具体含量受加工与配方影响。",
    "RECOMMENDED_FOR": "{source}与{target}相关的知识建议适用于该场景，实际执行应遵循专业指导。",
    "ADVICE": "知识库将{source}与{target}建议关联起来。",
    "ASSESSES": "{source}可用于评估{target}。",
    "MAY_ASSESS": "{source}可作为研究与{target}相关的评估指标，结果需结合背景解释。",
    "MEASURES": "{source}可用于测量或反映{target}。",
    "CONTRIBUTES_TO_ASSESSMENT": "{source}是{target}评估的一个信息维度。",
    "GUIDES": "{source}用于指导{target}。",
    "TARGETS": "{source}以{target}为关注结局。",
    "MAY_SUPPORT": "{source}可能支持{target}，但不能替代个体化治疗。",
    "HAS_OUTCOME": "{source}记录了{target}这一研究结局。",
    "STUDIES": "{source}研究了{target}。",
    "RECOMMENDS": "{source}包含与{target}相关的推荐主题。",
    "MEASURES_IN_STUDY": "{source}在研究中使用或测量{target}。",
    "REQUIRES_ASSESSMENT_FOR": "{source}在{target}方面通常需要专业评估。",
    "BELONGS_TO_TOPIC": "{source}归属于{target}相关主题。",
    "RELATED_TO": "{source}与{target}存在知识库关联。",
    "DEMO_RELATED_TO": "{source}与{target}是演示主题关联。",
    "CAN_ASSESS": "{source}可用于评估{target}。",
}


INTENT_PREDICATES = {
    "functions": {"SUPPORTS", "PARTICIPATES_IN", "ACTIVATES", "DISRUPTS", "CAN_CAUSE", "CAN_ALTER"},
    "food_sources": {"CONTAINS", "RICH_IN", "MAY_CONTAIN", "RELATED_TO"},
    "drug_interactions": {
        "INTERACTS_WITH",
        "INHIBITS",
        "CAN_ALTER",
        "CAN_CONTRIBUTE_TO",
        "ASSOCIATED_WITH",
        "REQUIRES_ASSESSMENT_FOR",
    },
    "deficiency": {
        "CAN_CAUSE",
        "CAN_CONTRIBUTE_TO",
        "AT_RISK",
        "DISRUPTS",
        "REQUIRES_ASSESSMENT_FOR",
    },
    "lab_tests": {
        "ASSESSES",
        "MAY_ASSESS",
        "MEASURES",
        "CONTRIBUTES_TO_ASSESSMENT",
        "MEASURES_IN_STUDY",
    },
    "recommendations": {
        "RECOMMENDED_FOR",
        "ADVICE",
        "GUIDES",
        "RECOMMENDS",
        "MAY_SUPPORT",
    },
    "research": {"HAS_OUTCOME", "STUDIES", "MEASURES_IN_STUDY", "RECOMMENDS"},
    "definition": {
        "IS_FORM_OF",
        "SUPPORTS",
        "PARTICIPATES_IN",
        "CONTAINS",
        "RICH_IN",
    },
}


@dataclass
class RetrievedFact:
    edge: GraphEdge
    neighbor: GraphNode
    direction: str


class GraphAnswerEngine:
    def __init__(
        self,
        settings: Settings,
        snapshot: SnapshotContext,
    ):
        self.settings = settings
        self.snapshot = snapshot
        self.metadata: MetadataStore = snapshot.metadata
        self.graph: KuzuGraphStore = snapshot.graph
        self.vectors: ChromaVectorStore = snapshot.vectors

    @staticmethod
    def normalize(query: str) -> str:
        normalized = re.sub(r"\s+", "", query.strip().lower())
        replacements = {
            "维生素 k": "维生素k",
            "维他命k": "维生素k",
            "维k": "维生素k",
            "phylloquinone": "维生素k1",
            "menaquinone": "维生素k2",
            "inr": "国际标准化比值",
            "pt": "凝血酶原时间",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        return normalized

    def answer(self, query: str, session_id: str | None = None) -> Answer:
        started = time.perf_counter()
        session_id = self.metadata.create_session(
            session_id if self.metadata.session_exists(session_id or "") else None,
            self.settings.session_ttl_hours,
        )
        normalized = self.normalize(query)
        self.metadata.add_message(session_id, "user", query)

        safety = self._safety_check(query)
        if safety:
            notice, safety_intent = safety
            answer = Answer(
                session_id=session_id,
                query=query,
                normalized_query=normalized,
                intent=safety_intent,
                answer_text=notice,
                sufficiency=EvidenceSufficiency.NONE,
                safety_notice=notice,
                data_version=self.snapshot.data_version,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
            self._finish_answer(answer)
            return answer

        prior_entities = self._prior_entities(session_id)
        entities = self._link_entities(query)
        if not entities and prior_entities:
            entities = [node for node in prior_entities if self.graph.get_node(node.id)]

        intent = self._detect_intent(query)
        facts, paths = self._retrieve_facts(entities, intent, query)
        if facts and not paths:
            paths = self._facts_as_paths(facts)
        related = self._related_entities(query, entities)

        if not facts and not paths:
            answer_text = (
                "当前知识库没有足够证据回答这个问题。"
                "系统不会使用生成模型补写医学结论。你可以查看下面的相关实体，或换一种更具体的问法。"
            )
            answer = Answer(
                session_id=session_id,
                query=query,
                normalized_query=normalized,
                intent=intent,
                answer_text=answer_text,
                sufficiency=EvidenceSufficiency.NONE,
                related_entities=related,
                data_version=self.snapshot.data_version,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
            self._finish_answer(answer)
            return answer

        claims = self._build_claims(facts, paths)
        citations = self._citations_for_claims(claims)
        sufficiency = (
            EvidenceSufficiency.SUFFICIENT
            if len(claims) >= 2 or (entities and len(claims) >= 1)
            else EvidenceSufficiency.PARTIAL
        )
        heading = self._heading(intent, entities)
        body = "\n".join(f"- {claim.text}" for claim in claims)
        caution = ""
        if intent in {"drug_interactions", "deficiency", "recommendations"}:
            caution = "\n\n涉及个体用药、诊断或治疗时，请咨询医生或药师；本回答仅整理知识库证据。"
        if sufficiency == EvidenceSufficiency.PARTIAL:
            caution += "\n\n当前证据只覆盖问题的一部分，未覆盖内容不作推测。"
        answer_text = f"{heading}\n\n{body}{caution}".strip()

        answer = Answer(
            session_id=session_id,
            query=query,
            normalized_query=normalized,
            intent=intent,
            answer_text=answer_text,
            claims=claims,
            citations=citations,
            graph_paths=paths,
            sufficiency=sufficiency,
            related_entities=related[:6],
            data_version=self.snapshot.data_version,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        self._finish_answer(answer)
        return answer

    def _finish_answer(self, answer: Answer) -> None:
        self.metadata.add_message(
            answer.session_id,
            "assistant",
            answer.answer_text,
            {
                "intent": answer.intent,
                "entities": [
                    node.id for path in answer.graph_paths for node in path.nodes
                ][:6],
                "evidence_ids": [citation.id for citation in answer.citations],
            },
        )
        self.metadata.log_query(
            answer.session_id,
            answer.query,
            answer.intent,
            answer.sufficiency.value,
            answer.elapsed_ms,
            answer.data_version.version,
        )

    def _safety_check(self, query: str) -> tuple[str, str] | None:
        compact = re.sub(r"\s+", "", query)
        for terms, message, intent in SAFETY_RULES:
            if any(term in compact for term in terms):
                return message, intent
        return None

    def _detect_intent(self, query: str) -> str:
        lowered = query.lower()
        scores: list[tuple[int, str]] = []
        for intent, keywords in INTENT_RULES:
            score = sum(1 for keyword in keywords if keyword.lower() in lowered)
            if score:
                scores.append((score, intent))
        if not scores:
            return "general"
        scores.sort(reverse=True)
        return scores[0][1]

    def _link_entities(self, query: str) -> list[GraphNode]:
        normalized = self.normalize(query)
        matched: list[tuple[int, int, GraphNode]] = []
        for node in self.graph.all_nodes():
            aliases = [node.name, node.id, *node.aliases]
            for alias in aliases:
                candidate = self.normalize(alias)
                if not candidate:
                    continue
                start = normalized.find(candidate)
                while start >= 0:
                    matched.append((len(candidate), start, node))
                    start = normalized.find(candidate, start + 1)
        matched.sort(key=lambda item: (-item[0], item[1]))
        output: list[GraphNode] = []
        accepted_spans: list[tuple[int, int]] = []
        for length, start, node in matched:
            end = start + length
            if any(start < existing_end and end > existing_start for existing_start, existing_end in accepted_spans):
                continue
            if node not in output:
                output.append(node)
                accepted_spans.append((start, end))
            if len(output) >= 4:
                break

        if output:
            return output

        best: list[tuple[float, GraphNode]] = []
        for node in self.graph.all_nodes():
            for alias in [node.name, *node.aliases]:
                ratio = SequenceMatcher(None, normalized, self.normalize(alias)).ratio()
                if ratio >= 0.62:
                    best.append((ratio, node))
        best.sort(key=lambda item: item[0], reverse=True)
        return [node for _, node in best[:2]]

    def _retrieve_facts(
        self,
        entities: list[GraphNode],
        intent: str,
        query: str,
    ) -> tuple[list[RetrievedFact], list[GraphPath]]:
        predicates = INTENT_PREDICATES.get(intent)
        if intent == "food_sources" and entities and entities[0].domain == "食物营养":
            facts = [
                RetrievedFact(edge, neighbor, direction)
                for edge, neighbor, direction in self.graph.neighbors(
                    entities[0].id,
                    {
                        "CONTAINS",
                        "RICH_IN",
                        "MAY_CONTAIN",
                        "RELATED_TO",
                    },
                )
            ]
            facts.sort(
                key=lambda item: (
                    0 if item.edge.predicate in {"CONTAINS", "RICH_IN", "MAY_CONTAIN"} else 1,
                    -item.edge.confidence,
                    item.neighbor.name,
                )
            )
            return facts[:8], []

        if len(entities) >= 2:
            paths: list[GraphPath] = []
            for left in entities[:2]:
                for right in entities[1:]:
                    if left.id == right.id:
                        continue
                    paths.extend(
                        self.graph.paths(
                            left.id,
                            right.id,
                            max_hops=self.settings.max_graph_hops,
                            limit=2,
                        )
                    )
            if paths:
                return [], paths

        if not entities:
            return [], []

        if intent == "general" and not self._is_general_followup(query, entities):
            return [], []

        facts: list[RetrievedFact] = []
        for entity in entities[:2]:
            for edge, neighbor, direction in self.graph.neighbors(entity.id, predicates):
                if intent == "food_sources" and entity.domain == "食物营养":
                    continue
                facts.append(RetrievedFact(edge, neighbor, direction))

        if not facts and intent == "general" and self._is_general_followup(query, entities):
            for entity in entities[:1]:
                for edge, neighbor, direction in self.graph.neighbors(entity.id):
                    facts.append(RetrievedFact(edge, neighbor, direction))

        facts.sort(key=lambda item: (-item.edge.confidence, item.neighbor.name))
        return facts[:12], []

    def _facts_as_paths(self, facts: list[RetrievedFact]) -> list[GraphPath]:
        output: list[GraphPath] = []
        seen_edges: set[str] = set()
        for fact in facts[:6]:
            if fact.edge.id in seen_edges:
                continue
            source = self.graph.get_node(fact.edge.source)
            target = self.graph.get_node(fact.edge.target)
            if not source or not target:
                continue
            seen_edges.add(fact.edge.id)
            output.append(
                GraphPath(
                    nodes=[source, target],
                    edges=[fact.edge],
                    evidence_ids=fact.edge.evidence_ids,
                )
            )
        return output

    def _is_general_followup(self, query: str, entities: list[GraphNode]) -> bool:
        if any(
            term in query
            for term in {"天气", "火星", "手机", "考试", "满分", "治愈所有", "替代所有"}
        ):
            return False
        residue = self.normalize(query)
        for node in entities:
            for alias in [node.name, node.id, *node.aliases]:
                residue = residue.replace(self.normalize(alias), "")
        residue = re.sub(r"[，。！？、,.!?和与及有什么关系统介绍一下的是什么]", "", residue)
        return len(residue) <= 4

    def _build_claims(
        self,
        facts: list[RetrievedFact],
        paths: list[GraphPath],
    ) -> list[Claim]:
        claims: list[Claim] = []
        seen: set[str] = set()

        for path in paths:
            for edge in path.edges:
                if not edge.evidence_ids:
                    continue
                source = self.graph.get_node(edge.source)
                target = self.graph.get_node(edge.target)
                if not source or not target:
                    continue
                text = self._edge_text(source, target, edge)
                if text in seen:
                    continue
                seen.add(text)
                claims.append(
                    Claim(
                        id=f"claim-{uuid.uuid4().hex[:10]}",
                        text=text,
                        evidence_ids=edge.evidence_ids[:3],
                        relation=edge.predicate,
                    )
                )

        for fact in facts:
            if not fact.edge.evidence_ids:
                continue
            edge_source = self.graph.get_node(fact.edge.source)
            edge_target = self.graph.get_node(fact.edge.target)
            if not edge_source or not edge_target:
                continue
            text = self._edge_text(edge_source, edge_target, fact.edge)
            if text in seen:
                continue
            seen.add(text)
            claims.append(
                Claim(
                    id=f"claim-{uuid.uuid4().hex[:10]}",
                    text=text,
                    evidence_ids=fact.edge.evidence_ids[:3],
                    relation=fact.edge.predicate,
                )
            )
            if len(claims) >= 8:
                break
        return claims[:8]

    @staticmethod
    def _edge_text(source: GraphNode, target: GraphNode, edge: GraphEdge) -> str:
        template = RELATION_TEXT.get(
            edge.predicate,
            "{source}与{target}通过“" + edge.predicate + "”关系关联。",
        )
        return template.format(source=source.name, target=target.name)

    def _citations_for_claims(self, claims: list[Claim]) -> list[Citation]:
        evidence_ids = list(dict.fromkeys(item for claim in claims for item in claim.evidence_ids))
        citations: list[Citation] = []
        for evidence in self.metadata.get_evidence_many(evidence_ids):
            citations.append(
                Citation(
                    id=evidence["id"],
                    source_id=evidence["source_id"],
                    source_title=evidence["title"],
                    source_type=evidence["source_type"],
                    publisher=evidence["publisher"],
                    published_at=evidence["published_at"],
                    url=evidence["url"],
                    evidence_level=evidence["evidence_level"],
                    locator=evidence["locator"],
                    snippet=evidence["chunk_text"],
                    is_demo=bool(evidence["is_demo"]),
                )
            )
        return citations

    def _related_entities(self, query: str, entities: list[GraphNode]) -> list[GraphNode]:
        output = list(entities)
        for node in self.graph.search_nodes(query, limit=8):
            if node not in output:
                output.append(node)
        if len(output) < 4 and entities:
            for _edge, neighbor, _ in self.graph.neighbors(entities[0].id):
                if neighbor not in output:
                    output.append(neighbor)
                if len(output) >= 8:
                    break
        return output[:8]

    def _prior_entities(self, session_id: str) -> list[GraphNode]:
        messages = self.metadata.get_recent_messages(session_id, limit=6)
        for message in reversed(messages):
            if message["role"] != "assistant":
                continue
            metadata = message.get("metadata_json")
            if not metadata:
                continue
            import json

            payload = json.loads(metadata)
            nodes = [
                node
                for entity_id in payload.get("entities", [])
                if (node := self.graph.get_node(entity_id))
            ]
            if nodes:
                return nodes
        return []

    @staticmethod
    def _heading(intent: str, entities: list[GraphNode]) -> str:
        subject = "、".join(node.name for node in entities[:2]) or "该问题"
        headings = {
            "food_sources": f"知识库中与{subject}相关的食物来源如下：",
            "drug_interactions": f"知识库中与{subject}相关的药物相互作用线索如下：",
            "deficiency": f"知识库中与{subject}相关的缺乏和风险信息如下：",
            "functions": f"知识库中与{subject}相关的功能信息如下：",
            "lab_tests": f"知识库中与{subject}相关的检测信息如下：",
            "recommendations": f"知识库中与{subject}相关的建议信息如下：",
            "research": f"知识库中与{subject}相关的研究证据信息如下：",
            "comparison": f"知识库中关于{subject}的关系路径如下：",
            "definition": f"知识库中关于{subject}的结构化信息如下：",
        }
        return headings.get(intent, f"知识库中与{subject}相关的证据如下：")
