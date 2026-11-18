from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

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

MEDICATION_SAFETY_PATTERNS = [
    re.compile(
        r"(华法林|抗凝药).{0,20}(多少|几片|几粒|几毫克|剂量|毫克|mg)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(我|本人|患者|孩子|老人|孕妇).{0,16}(吃|服用|补充|摄入|用药)"
        r".{0,16}(多少|几片|几粒|几毫克|剂量|毫克|mg)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(怎么|可以|能|需要|想).{0,8}(停药|停用|换药|加量|减量)",
        re.IGNORECASE,
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
    "no_significant_interaction_observed_with": "当前队列分析未观察到{source}与{target}之间存在显著交互。",
    "no_significant_association_observed_with": "当前队列分析未观察到{source}与{target}之间存在显著关联。",
    "no_supported_mediation_via": "当前分析未支持{source}通过{target}形成中介路径。",
    "moderates_effect_on": "{source}对{target}表现出调节作用。",
    "cross_sectionally_associated_with": "{source}与{target}存在横断面关联。",
    "has_longitudinal_effect_on": "{source}与{target}存在纵向效应关联。",
    "shows_dose_response_with": "{source}与{target}呈现剂量反应关系。",
    "modulates_postprandial_kinetics_of": "{source}与{target}的餐后动力学变化相关。",
}

REAL_PREDICATE_TEXT = {
    "contains": "含有或存在于",
    "is_antagonized_by": "受到拮抗或存在拮抗关系",
    "deficiency_causes": "缺乏可导致",
    "excess_causes": "过量可导致",
    "regulates_expression_of": "调节表达",
    "activates_protein": "参与或激活蛋白功能",
    "has_outcome_biomarker": "关联结局指标",
    "indicates_risk_of": "提示风险",
    "cross_sectionally_associated_with": "存在横断面关联",
    "participates_in_cycle": "参与循环",
    "is_carboxylated_by": "参与羧化",
    "measured_by": "通过该指标测量",
    "reflects_status_of": "反映状态",
    "is_synthesized_by": "合成来源",
    "targets_tissue": "作用于组织",
    "prevents": "预防",
    "increases": "增加",
    "reduces": "降低",
    "affects": "影响",
    "has_subject": "研究对象或人群",
    "requires": "需要",
    "supported_by": "研究类型支持",
    "has_exposure_intervention": "暴露或干预",
    "has_exposure_dose_record": "暴露剂量记录",
    "measured_vitamin_k_form": "测量维生素 K 形式",
}

ENTITY_LABELS = {
    "vitamin k": "维生素K",
    "vitamin k1": "维生素K1",
    "phylloquinone": "叶绿醌（维生素K1）",
    "vitamin k2": "维生素K2",
    "menaquinone": "甲萘醌类（维生素K2）",
    "mk-7": "MK-7",
    "mk-4": "MK-4",
    "warfarin": "华法林",
    "osteocalcin": "骨钙素",
    "matrix gla protein": "基质Gla蛋白",
    "dp-ucmgp": "dp-ucMGP",
    "ucoc": "未羧化骨钙素（ucOC）",
    "pivka-ii": "PIVKA-II",
    "green leafy vegetables": "深绿色叶菜",
    "plant oil": "植物油",
    "vegetable oils": "植物油",
    "fermented soy products": "发酵豆制品",
    "vkorc1": "VKORC1",
    "ggcx": "GGCX",
    "insulin": "胰岛素",
    "homa-ir": "HOMA-IR",
}


def display_entity(value: str) -> str:
    key = re.sub(r"\s+", " ", value or "").strip().lower()
    if key in ENTITY_LABELS:
        return ENTITY_LABELS[key]
    if "green leafy" in key:
        return "深绿色叶菜"
    if "plant oil" in key or "vegetable oil" in key:
        return "植物油"
    if "phylloquinone" in key:
        return "叶绿醌（维生素K1）"
    if "menaquinone" in key:
        return "甲萘醌类（维生素K2）"
    return value


def equivalent_entity_key(value: str) -> str:
    key = re.sub(r"\s+", " ", value or "").strip().lower()
    if key == "vitamin k1" or "phylloquinone" in key:
        return "vitamin-k1"
    if key in {"vitamin k2", "menaquinone", "menaquinones"}:
        return "vitamin-k2"
    return key


def natural_evidence_sentence(subject: str, predicate: str, target: str) -> str:
    source = display_entity(subject)
    object_name = display_entity(target)
    template = RELATION_TEXT.get(predicate)
    if template:
        return template.format(source=source, target=object_name)
    if predicate == "contains":
        return f"{source}与{object_name}之间存在食物来源关系。"
    if predicate == "is_synthesized_by":
        return f"{source}可从{object_name}中获得，或与{object_name}有关。"
    if predicate == "is_antagonized_by":
        return f"{source}与{object_name}存在拮抗关系。"
    if predicate == "deficiency_causes":
        return f"{source}缺乏可能导致{object_name}。"
    if predicate == "excess_causes":
        return f"{source}过量可能与{object_name}有关。"
    if predicate == "regulates_expression_of":
        return f"{source}参与调节{object_name}。"
    if predicate == "activates_protein":
        return f"{source}参与{object_name}的活化或羧化。"
    if predicate == "has_outcome_biomarker":
        return f"{source}相关研究关注{object_name}这一结局或指标。"
    if predicate == "measured_by":
        return f"{source}可以通过{object_name}进行评估。"
    if predicate == "reflects_status_of":
        return f"{source}可以反映{object_name}的状态。"
    if predicate == "indicates_risk_of":
        return f"研究提示{source}与{object_name}风险相关。"
    if predicate == "targets_tissue":
        return f"{source}与{object_name}等组织或部位有关。"
    if predicate == "supported_by":
        return f"关于{source}的证据来自{object_name}。"
    if predicate == "cross_sectionally_associated_with":
        return f"横断面分析显示{source}与{object_name}存在关联。"
    if predicate == "has_longitudinal_effect_on":
        return f"纵向分析提示{source}与{object_name}存在效应关联。"
    if predicate == "shows_dose_response_with":
        return f"分析显示{source}与{object_name}之间存在剂量反应关系。"
    if predicate.startswith("no_"):
        return f"当前分析未观察到{source}与{object_name}之间存在明确显著关系。"
    return f"现有证据记录了{source}与{object_name}之间的关系。"


def human_opening(intent: str, internal: bool) -> str:
    if internal:
        return "从本项目内部队列的分析结果看，可以确认以下信息。"
    openings = {
        "food_sources": "维生素K的食物来源可以从不同维生素K形式来理解。",
        "drug_interactions": "这类问题的重点是药物与维生素K之间的药理作用、饮食影响和监测要求。",
        "deficiency": "维生素K不足主要会影响依赖维生素K的凝血和骨代谢相关过程。",
        "functions": "维生素K在体内主要作为多种蛋白质活化所需的辅因子。",
        "lab_tests": "这个指标通常需要结合它反映的生理过程和具体检测背景来解释。",
        "recommendations": "相关建议需要区分一般营养信息和个体化医疗决定。",
        "research": "从现有真实研究看，证据主要集中在研究人群、干预方式和结局指标上。",
        "comparison": "比较不同维生素K形式时，需要同时看食物来源、化学结构和生理作用。",
        "definition": "维生素K不是一个单一化合物，而是一组结构相关、功能重要的脂溶性维生素。",
    }
    return openings.get(intent, "从现有真实证据看，可以确认以下信息。")


def human_closing(intent: str, internal: bool) -> str:
    if internal:
        return "这些结果属于内部队列的统计关联或阴性发现，不能直接等同于临床因果结论。"
    closings = {
        "food_sources": "食物中的维生素K含量会受品种、部位、加工和烹饪方式影响，实际饮食应结合个人情况安排。",
        "drug_interactions": "如果正在使用华法林等抗凝药，不要仅凭一次问答自行调整饮食、补充剂或用药。",
        "deficiency": "是否存在缺乏需要结合膳食、症状、用药和实验室检查由专业人员判断。",
        "functions": "这些机制说明维生素K的重要性，但不能直接推导出某种补充剂适合所有人。",
        "lab_tests": "检测结果需要结合参考区间、检测方法和临床背景解释。",
        "recommendations": "涉及孕妇、儿童、老年人或用药人群时，应由医生或药师给出个体化建议。",
        "research": "研究结果提示的是证据方向，不等同于已经形成面向所有人的临床治疗建议。",
        "comparison": "不同形式不能简单按“哪一种更好”判断，应结合具体健康目标和证据场景。",
        "definition": "以上是当前真实证据能够支持的基础解释。",
    }
    return closings.get(intent, "以上内容仅代表当前真实证据能够支持的范围。")


QUERY_EXPANSIONS = [
    ("华法林", ("Warfarin", "antagonist")),
    ("维生素k", ("Vitamin K", "phylloquinone", "menaquinone")),
    ("维生素 k", ("Vitamin K", "phylloquinone", "menaquinone")),
    ("骨钙素", ("Osteocalcin", "carboxylation")),
    ("血管钙化", ("vascular calcification", "matrix Gla protein")),
    ("缺乏", ("deficiency", "deficient", "bleeding")),
    ("食物", ("food", "diet", "vegetable", "leafy", "oil")),
    ("来源", ("food", "diet", "vegetable", "leafy", "oil")),
    ("检测", ("plasma", "serum", "biomarker", "measured")),
    ("指标", ("plasma", "serum", "biomarker", "measured")),
    ("新生儿", ("newborn", "infant", "neonatal")),
    ("孕妇", ("pregnancy", "pregnant", "maternal")),
    ("胰岛素", ("insulin",)),
    ("血糖", ("glucose", "GLU")),
    ("糖化", ("HbA1c",)),
    ("维生素d", ("vitamin D",)),
    ("肥胖", ("obesity", "BMI")),
    ("内部", ("VK1", "MK-7", "MK-4", "GLU")),
    ("队列", ("VK1", "MK-7", "MK-4", "GLU")),
    ("绿叶蔬菜", ("green leafy vegetables", "vegetable", "leafy")),
    ("mk-7", ("MK-7", "menaquinone-7")),
    ("pivka", ("PIVKA-II", "proteins induced by vitamin K absence")),
]


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
            "维k": "维生素k",
            "phylloquinone": "维生素k1",
            "menaquinone": "维生素k2",
            "inr": "国际标准化比值",
            "pt": "凝血酶原时间",
            "维生素k": "vitamink",
            "维他命k": "vitamink",
            "叶绿醌": "phylloquinone",
            "甲萘醌": "menaquinone",
            "华法林": "warfarin",
            "骨钙素": "osteocalcin",
            "胰岛素": "insulin",
            "血糖": "glucose",
            "维生素d": "vitamind",
            "基质gla蛋白": "matrixglaprotein",
            "异常凝血酶原": "pivkaii",
            "绿叶蔬菜": "greenleafyvegetables",
            "深绿色叶菜": "greenleafyvegetables",
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
        related = self._related_entities(query, entities)
        if not self.snapshot.data_version.is_demo:
            forms_answer = self._vitamin_k_forms_answer(
                query=query,
                normalized=normalized,
                session_id=session_id,
                intent=intent,
                entities=entities,
                related=related,
                started=started,
            )
            if forms_answer:
                return forms_answer
            synthesized = self._warfarin_vitamin_k_answer(
                query=query,
                normalized=normalized,
                session_id=session_id,
                intent=intent,
                entities=entities,
                related=related,
                started=started,
            )
            if synthesized:
                return synthesized
            text_answer = self._text_evidence_answer(
                query=query,
                normalized=normalized,
                session_id=session_id,
                intent=intent,
                entities=entities,
                related=related,
                started=started,
            )
            if text_answer:
                return text_answer

        facts, paths = self._retrieve_facts(entities, intent, query)
        if facts and not paths:
            paths = self._facts_as_paths(facts)

        if not facts and not paths:
            text_answer = self._text_evidence_answer(
                query=query,
                normalized=normalized,
                session_id=session_id,
                intent=intent,
                entities=entities,
                related=related,
                started=started,
            )
            if text_answer:
                return text_answer
            answer_text = (
                "我查了当前知识库，暂时没有找到足够可靠的证据来回答这个问题。"
                "为了避免猜测医学结论，我不会继续补充。"
                "你可以换一种更具体的问法，或查看下面的相关实体。"
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
        if not claims:
            text_answer = self._text_evidence_answer(
                query=query,
                normalized=normalized,
                session_id=session_id,
                intent=intent,
                entities=entities,
                related=related,
                started=started,
            )
            if text_answer:
                return text_answer
            answer_text = (
                "我找到了相关资料，但它们还没有达到可以正式回答的审核标准。"
                "你可以到研究检索中查看候选证据，我不会把待审核内容当成确定结论。"
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
        for pattern in MEDICATION_SAFETY_PATTERNS:
            if pattern.search(compact):
                return SAFETY_RULES[1][1], "medication"
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
        matched: list[tuple[int, int, int, GraphNode]] = []
        for node in self.graph.all_nodes():
            source_priority = 0 if node.id.startswith("ENT_") else 1
            aliases = [node.name, node.id, *node.aliases]
            for alias in aliases:
                candidate = self.normalize(alias)
                if not candidate:
                    continue
                start = normalized.find(candidate)
                while start >= 0:
                    matched.append((len(candidate), start, source_priority, node))
                    start = normalized.find(candidate, start + 1)
        matched.sort(key=lambda item: (-item[0], item[1], item[2]))
        output: list[GraphNode] = []
        accepted_spans: list[tuple[int, int]] = []
        for length, start, _priority, node in matched:
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

    @staticmethod
    def _expanded_text_query(query: str) -> str:
        lowered = query.lower()
        terms: list[str] = []
        for trigger, expansions in QUERY_EXPANSIONS:
            if trigger in lowered:
                terms.extend(expansions)
        terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", query))
        return " ".join(dict.fromkeys(term for term in terms if term))

    def _text_evidence_answer(
        self,
        *,
        query: str,
        normalized: str,
        session_id: str,
        intent: str,
        entities: list[GraphNode],
        related: list[GraphNode],
        started: float,
    ) -> Answer | None:
        expanded_query = self._expanded_text_query(query)
        if not expanded_query:
            return None
        query_lower = query.lower()
        source_types: set[str] | None = None
        if "内部" in query_lower or "队列" in query_lower:
            source_types = {"internal"}
        elif "外部" in query_lower or "文献" in query_lower:
            source_types = {"literature", "structured"}
        rows = self.metadata.search_fts(
            expanded_query,
            limit=24,
            source_types=source_types,
        )

        evidence_ids = list(
            dict.fromkeys(
                str(row["evidence_id"])
                for row in rows
                if row.get("evidence_id")
                and bool(row.get("answer_eligible", 1))
            )
        )
        if not evidence_ids:
            return None

        entity_names = {
            self.normalize(value)
            for node in entities
            for value in [node.name, *node.aliases]
            if value
        }

        def matches_entity(label: str) -> bool:
            candidate = self.normalize(label)
            return any(
                name == candidate
                or (len(name) >= 5 and candidate.startswith(name))
                for name in entity_names
            )

        prepared: list[tuple[int, str, dict[str, Any], dict[str, Any]]] = []
        for evidence in self.metadata.get_evidence_many(evidence_ids[:24]):
            try:
                metadata = json.loads(evidence.get("metadata_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                metadata = {}
            subject = str(metadata.get("subject_label") or "").strip()
            target = str(metadata.get("object_label") or "").strip()
            match_count = int(matches_entity(subject)) + int(matches_entity(target))
            if entities and match_count == 0:
                continue
            prepared.append((match_count, str(evidence["id"]), evidence, metadata))

        if entities and len(entities) >= 2:
            pair_matches = [item for item in prepared if item[0] >= 2]
            if pair_matches:
                prepared = pair_matches
        prepared.sort(
            key=lambda item: (
                -item[0],
                0 if item[2].get("source_type") == "internal" and "内部" in query else 1,
            )
        )

        claims: list[Claim] = []
        seen_claims: set[str] = set()
        origins: set[str] = set()
        for _match_count, evidence_id, evidence, metadata in prepared:
            subject = str(metadata.get("subject_label") or "").strip()
            predicate = str(metadata.get("predicate") or "").strip()
            target = str(metadata.get("object_label") or "").strip()
            if not subject or not predicate or not target:
                continue
            if equivalent_entity_key(subject) == equivalent_entity_key(target):
                continue
            text = natural_evidence_sentence(subject, predicate, target)
            origin = str(evidence.get("data_origin") or "")
            if text in seen_claims:
                continue
            seen_claims.add(text)
            claims.append(
                Claim(
                    id=f"claim-{uuid.uuid4().hex[:10]}",
                    text=text,
                    evidence_ids=[evidence_id],
                    relation=predicate,
                )
            )
            origins.add(origin)
            if len(claims) >= 5:
                break

        if not claims:
            return None
        citations = self._citations_for_claims(claims)
        internal = "internal" in origins
        answer_text = (
            f"{human_opening(intent, internal)}\n\n"
            + "".join(claim.text for claim in claims)
            + f"\n\n{human_closing(intent, internal)}"
        )
        answer = Answer(
            session_id=session_id,
            query=query,
            normalized_query=normalized,
            intent=intent,
            answer_text=answer_text,
            claims=claims,
            citations=citations,
            sufficiency=(
                EvidenceSufficiency.SUFFICIENT
                if len(claims) >= 2
                else EvidenceSufficiency.PARTIAL
            ),
            related_entities=related[:6],
            data_version=self.snapshot.data_version,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        self._finish_answer(answer)
        return answer

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
                eligible_ids = self._answer_eligible_ids(edge.evidence_ids)
                if not eligible_ids:
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
                        evidence_ids=eligible_ids[:3],
                        relation=edge.predicate,
                    )
                )

        for fact in facts:
            eligible_ids = self._answer_eligible_ids(fact.edge.evidence_ids)
            if not eligible_ids:
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
                    evidence_ids=eligible_ids[:3],
                    relation=fact.edge.predicate,
                )
            )
            if len(claims) >= 8:
                break
        return claims[:8]

    def _answer_eligible_ids(self, evidence_ids: list[str]) -> list[str]:
        if not evidence_ids:
            return []
        return [
            evidence["id"]
            for evidence in self.metadata.get_evidence_many(evidence_ids)
            if bool(evidence.get("answer_eligible", 1))
        ]

    def _vitamin_k_forms_answer(
        self,
        *,
        query: str,
        normalized: str,
        session_id: str,
        intent: str,
        entities: list[GraphNode],
        related: list[GraphNode],
        started: float,
    ) -> Answer | None:
        if "vitamink" not in normalized:
            return None
        if not any(
            term in normalized
            for term in ("几种", "亚型", "类型", "分类", "形式")
        ):
            return None
        evidence_ids = self.metadata.search_evidence_phrases(
            [
                "two major forms of Vitamin K",
                "two main isoforms",
                "two main forms",
                "side chain",
                "menaquinone-n",
                "two subtypes of vitamin K2",
                "MK-4 and MK-7",
                "intermediate vitamin K3",
            ],
            limit=80,
            source_types={"literature"},
        )
        evidence_items = self.metadata.get_evidence_many(evidence_ids)

        def find(patterns: tuple[re.Pattern[str], ...]) -> dict[str, Any] | None:
            for pattern in patterns:
                for evidence in evidence_items:
                    text = (
                        f"{evidence.get('chunk_text', '')} "
                        f"{evidence.get('source_locator', '')}"
                    )
                    if pattern.search(text):
                        return evidence
            return None

        main_forms = find(
            (
                re.compile(r"two major forms of Vitamin K", re.IGNORECASE),
                re.compile(r"two main isoforms", re.IGNORECASE),
                re.compile(r"two main forms", re.IGNORECASE),
            )
        )
        k2_group = find(
            (
                re.compile(r"side chain.*units varying", re.IGNORECASE),
                re.compile(r"menaquinone-n.*MK-n", re.IGNORECASE),
                re.compile(r"side chain.*prenyl units", re.IGNORECASE),
            )
        )
        common_subtypes = find(
            (
                re.compile(
                    r"two subtypes of vitamin K2.*MK-4 and MK-7",
                    re.IGNORECASE,
                ),
                re.compile(r"MK-4 and MK-7.*clinical trials", re.IGNORECASE),
            )
        )
        k3_intermediate = find(
            (
                re.compile(r"intermediate vitamin K3", re.IGNORECASE),
                re.compile(
                    r"vitamin K3.*menadione.*intermediate",
                    re.IGNORECASE,
                ),
            )
        )
        selected = [
            evidence
            for evidence in (main_forms, k2_group, common_subtypes, k3_intermediate)
            if evidence
        ]
        if not main_forms or len(selected) < 3:
            return None

        claim_specs = [
            (
                "如果按营养学和当前文献里常用的分类，维生素K最核心的两大类是"
                "维生素K1和维生素K2。",
                [main_forms],
            ),
            (
                "维生素K1又叫叶绿醌或phytonadione；维生素K2属于甲萘醌类，"
                "是另一大类别。",
                [main_forms],
            ),
            (
                "K2内部按侧链中异戊二烯单位的数量命名，形成MK-4、MK-7、MK-8、"
                "MK-9等不同menaquinone亚型。",
                [k2_group],
            ),
            (
                "临床和营养研究中较常讨论的K2亚型是MK-4和MK-7。",
                [common_subtypes],
            ),
        ]
        if k3_intermediate:
            claim_specs.append(
                (
                    "K3（甲萘醌）更多作为合成或代谢中间体讨论，"
                    "不属于文献中并列的两大天然膳食形式。",
                    [k3_intermediate],
                )
            )
        claims = [
            Claim(
                id=f"claim-{uuid.uuid4().hex[:10]}",
                text=text,
                evidence_ids=[evidence["id"] for evidence in evidence_group if evidence],
                relation="vitamin_k_forms_synthesis",
            )
            for text, evidence_group in claim_specs
        ]
        answer = Answer(
            session_id=session_id,
            query=query,
            normalized_query=normalized,
            intent=intent,
            answer_text=(
                "如果按营养学和当前文献里常用的分类，维生素K最核心的两大类是"
                "维生素K1和维生素K2。\n\n"
                + "".join(claim.text for claim in claims[2:])
                + "\n\n所以，大类上通常说两种；但K2内部并不是单一物质，"
                "而是包含多个MK-n亚型。"
            ),
            claims=claims,
            citations=self._citations_for_claims(claims),
            sufficiency=EvidenceSufficiency.SUFFICIENT,
            related_entities=related[:6],
            data_version=self.snapshot.data_version,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        self._finish_answer(answer)
        return answer

    def _warfarin_vitamin_k_answer(
        self,
        *,
        query: str,
        normalized: str,
        session_id: str,
        intent: str,
        entities: list[GraphNode],
        related: list[GraphNode],
        started: float,
    ) -> Answer | None:
        if "warfarin" not in normalized or "vitamink" not in normalized:
            return None
        evidence_ids = self.metadata.search_evidence_phrases(
            [
                "VKORC1 inhibitor",
                "Vitamin K epoxide reductase",
                "By targeting VKOR",
                "large amounts of Vitamin K",
                "dark green leafy vegetables",
                "phytonadione",
                "low-dose Vitamin K",
                "coagulation monitoring",
            ],
            limit=100,
            source_types={"literature"},
        )
        evidence_items = self.metadata.get_evidence_many(evidence_ids)

        def find(patterns: tuple[re.Pattern[str], ...]) -> dict[str, Any] | None:
            for pattern in patterns:
                for evidence in evidence_items:
                    text = (
                        f"{evidence.get('chunk_text', '')} "
                        f"{evidence.get('source_locator', '')}"
                    )
                    if pattern.search(text):
                        return evidence
            return None

        mechanism = find(
            (
                re.compile(r"VKORC1 inhibitor.*reduced Vitamin K", re.IGNORECASE),
                re.compile(
                    r"Vitamin K epoxide reductase.*Vitamin K hydroquinone",
                    re.IGNORECASE,
                ),
                re.compile(r"By targeting VKOR.*coagulation proteins", re.IGNORECASE),
            )
        )
        food_effect = find(
            (
                re.compile(r"large amounts of Vitamin K.*lower the INR", re.IGNORECASE),
                re.compile(r"dark green leafy vegetables.*INR", re.IGNORECASE),
            )
        )
        reversal = find(
            (
                re.compile(r"low-dose Vitamin K.*managed", re.IGNORECASE),
                re.compile(
                    r"phytonadione.*excessive anticoagulation",
                    re.IGNORECASE,
                ),
            )
        )
        monitoring = find(
            (
                re.compile(r"coagulation monitoring", re.IGNORECASE),
                re.compile(r"monitoring.*INR", re.IGNORECASE),
            )
        )
        selected = [
            evidence
            for evidence in (mechanism, food_effect, reversal, monitoring)
            if evidence
        ]
        if not mechanism or len(selected) < 3:
            return None

        claim_specs = [
            (
                "华法林通过抑制 VKORC1，阻断维生素 K 环氧化物还原，"
                "减少活性维生素 K 的再生，并影响维生素 K 依赖凝血因子的活化。",
                [mechanism],
            ),
            (
                "两者是明确的药理学拮抗关系：维生素 K 摄入或补充会影响华法林的"
                "抗凝强度，需要结合 INR 和用药情况管理。",
                [food_effect, reversal],
            ),
        ]
        if food_effect:
            claim_specs.append(
                (
                    "富含维生素 K 的食物，例如菠菜、羽衣甘蓝等深绿色叶菜，"
                    "可能降低 INR。",
                    [food_effect],
                )
            )
        if reversal:
            claim_specs.append(
                (
                    "华法林抗凝过度时，维生素 K 可在专业评估下用于纠正凝血状态，"
                    "具体处理取决于 INR、出血情况和临床背景。",
                    [reversal],
                )
            )
        if monitoring:
            claim_specs.append(
                (
                    "华法林使用期间需要按医嘱监测 INR，并尽量保持日常维生素 K "
                    "摄入相对稳定，不应自行改变补充剂或摄入量。",
                    [monitoring],
                )
            )

        claims = [
            Claim(
                id=f"claim-{uuid.uuid4().hex[:10]}",
                text=text,
                evidence_ids=[
                    evidence["id"] for evidence in evidence_group if evidence
                ],
                relation="warfarin_vitamin_k_synthesis",
            )
            for text, evidence_group in claim_specs
            if any(evidence_group)
        ]
        answer = Answer(
            session_id=session_id,
            query=query,
            normalized_query=normalized,
            intent=intent,
            answer_text=(
                "华法林与维生素 K 属于明确的药理学拮抗关系，"
                "需要结合机制、饮食和 INR 监测理解。\n\n"
                + "".join(claim.text for claim in claims)
                + "\n\n以上结论由真实外部文献证据合成，具体剂量调整、停药或"
                "抗凝过度处理必须由医生或药师评估。"
            ),
            claims=claims,
            citations=self._citations_for_claims(claims),
            sufficiency=EvidenceSufficiency.SUFFICIENT,
            related_entities=related[:6],
            data_version=self.snapshot.data_version,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        self._finish_answer(answer)
        return answer

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
                    source_classification=evidence["source_classification"],
                    data_origin=evidence["data_origin"],
                    data_owner=evidence["data_owner"],
                    access_scope=evidence["access_scope"],
                    publisher=evidence["publisher"],
                    published_at=evidence["published_at"],
                    url=evidence["url"],
                    evidence_level=evidence["evidence_level"],
                    locator=evidence["locator"],
                    snippet=evidence["chunk_text"],
                    is_demo=bool(evidence["is_demo"]),
                    review_status=evidence["review_status"] or "",
                    input_status=evidence["input_status"] or "",
                    fusion_status=evidence["fusion_status"] or "",
                    evidence_status=evidence["evidence_status"] or "",
                    source_version=evidence["source_version"] or "",
                    source_locator=evidence["source_locator"] or "",
                    analysis_context=json.loads(evidence["metadata_json"] or "{}").get(
                        "analysis_context",
                        "",
                    ),
                    effect_size=json.loads(evidence["metadata_json"] or "{}").get(
                        "effect_size",
                        "",
                    ),
                    p_value=json.loads(evidence["metadata_json"] or "{}").get(
                        "p_value",
                        "",
                    ),
                    q_value=json.loads(evidence["metadata_json"] or "{}").get(
                        "q_value",
                        "",
                    ),
                    sample_n=json.loads(evidence["metadata_json"] or "{}").get(
                        "sample_n",
                        "",
                    ),
                    model_type=json.loads(evidence["metadata_json"] or "{}").get(
                        "model_type",
                        "",
                    ),
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
