from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock

from app.config import Settings
from app.schemas import (
    Citation,
    Claim,
    TriageAnswerRequest,
    TriageOption,
    TriageOutcome,
    TriageProgress,
    TriageQuestion,
    TriageSessionResponse,
)
from app.services.qa import METADATA_ONLY_ANSWER_PREDICATES, GraphAnswerEngine
from app.services.snapshot import SnapshotContext

TRIAGE_TTL_SECONDS = 24 * 60 * 60
EMERGENCY_VALUES = {"active_bleeding", "black_stool", "severe_headache"}
PROFESSIONAL_VALUES = {
    "fat_malabsorption",
    "cholestasis_liver",
    "gi_surgery",
    "warfarin",
    "long_antibiotics",
    "other_long_term_medication",
    "newborn",
    "pregnancy",
    "breastfeeding",
    "abnormal_vitamin_k_lab",
    "abnormal_inr",
    "unsure",
}


def _question(
    question_id: str,
    prompt: str,
    help_text: str,
    options: list[tuple[str, str, str]],
    *,
    multiple: bool = False,
) -> TriageQuestion:
    return TriageQuestion(
        id=question_id,
        prompt=prompt,
        help_text=help_text,
        multiple=multiple,
        options=[
            TriageOption(value=value, label=label, description=description)
            for value, label, description in options
        ],
    )


QUESTIONS = [
    _question(
        "symptoms",
        "最近是否出现以下需要优先处理的情况？",
        "可以选择多项。如存在活动性出血或急性神经系统症状，请优先就医。",
        [
            ("active_bleeding", "持续或不明原因出血", "例如伤口持续渗血、鼻血难以停止"),
            ("black_stool", "黑便、血便或呕血", "可能需要紧急评估"),
            ("severe_headache", "严重头痛或急性神经系统症状", "包括突发剧烈头痛、意识异常"),
            ("none", "以上都没有", ""),
            ("unsure", "不确定", "无法判断时按需专业评估处理"),
        ],
        multiple=True,
    ),
    _question(
        "conditions",
        "是否有医生诊断过影响维生素K吸收或利用的情况？",
        "不需要填写具体病名，可多选。",
        [
            ("fat_malabsorption", "脂肪吸收不良", "如长期脂肪泻或吸收障碍"),
            ("cholestasis_liver", "胆汁淤积或肝胆疾病", ""),
            ("gi_surgery", "胃肠道手术或短肠情况", ""),
            ("none", "没有", ""),
            ("unsure", "不确定", ""),
        ],
        multiple=True,
    ),
    _question(
        "medications",
        "是否正在使用以下药物？",
        "仅用于判断是否需要专业评估，不会生成剂量建议。",
        [
            ("warfarin", "华法林或其他抗凝药", ""),
            ("long_antibiotics", "长期抗生素", ""),
            ("other_long_term_medication", "其他长期药物", ""),
            ("none", "没有", ""),
            ("unsure", "不确定", ""),
        ],
        multiple=True,
    ),
    _question(
        "special_population",
        "这个问题是否涉及以下人群？",
        "",
        [
            ("newborn", "新生儿", ""),
            ("pregnancy", "孕期", ""),
            ("breastfeeding", "哺乳期", ""),
            ("none", "都不涉及", ""),
            ("unsure", "不确定", ""),
        ],
        multiple=True,
    ),
    _question(
        "diet",
        "最近的饮食中，深绿色叶菜、植物油或发酵豆制品摄入如何？",
        "这里仅做膳食背景了解，不据此诊断缺乏。",
        [
            ("very_low_green_vegetables", "长期很少摄入", ""),
            ("prolonged_low_intake", "整体进食量长期不足", ""),
            ("normal", "基本正常", ""),
            ("unsure", "不确定", ""),
        ],
    ),
    _question(
        "labs",
        "是否已有与维生素K相关的检测结果？",
        "包括 INR、PIVKA-II、ucOC、dp-ucMGP 或维生素K水平。",
        [
            ("abnormal_vitamin_k_lab", "有，结果异常", ""),
            ("abnormal_inr", "有，INR异常", ""),
            ("normal", "有，结果正常", ""),
            ("none", "没有检测", ""),
            ("unsure", "不确定", ""),
        ],
    ),
    _question(
        "supplement",
        "目前是否正在补充维生素K？",
        "系统不会根据该回答调整或停止任何补充方案。",
        [
            ("regular", "规律补充", ""),
            ("occasional", "偶尔补充", ""),
            ("none", "没有补充", ""),
            ("unsure", "不确定", ""),
        ],
    ),
]


@dataclass
class TriageState:
    session_id: str
    created_at: float
    updated_at: float
    answers: dict[str, list[str]] = field(default_factory=dict)
    index: int = 0
    outcome: TriageOutcome | None = None


class TriageService:
    def __init__(self, settings: Settings, snapshot: SnapshotContext):
        self.settings = settings
        self.snapshot = snapshot
        self.engine = GraphAnswerEngine(settings, snapshot)
        self._sessions: dict[str, TriageState] = {}
        self._lock = Lock()

    def start(self) -> TriageSessionResponse:
        with self._lock:
            self._purge_expired()
            now = time.time()
            state = TriageState(
                session_id=f"triage-{uuid.uuid4()}",
                created_at=now,
                updated_at=now,
            )
            self._sessions[state.session_id] = state
            return self._response(state)

    def rebind(self, snapshot: SnapshotContext) -> None:
        with self._lock:
            self.snapshot = snapshot
            self.engine = GraphAnswerEngine(self.settings, snapshot)
            self._sessions.clear()

    def get(self, session_id: str) -> TriageSessionResponse | None:
        with self._lock:
            self._purge_expired()
            state = self._sessions.get(session_id)
            return self._response(state) if state else None

    def answer(
        self,
        session_id: str,
        payload: TriageAnswerRequest,
    ) -> TriageSessionResponse | None:
        with self._lock:
            self._purge_expired()
            state = self._sessions.get(session_id)
            if state is None:
                return None
            if state.outcome is not None:
                return self._response(state)
            question = QUESTIONS[state.index]
            if payload.question_id != question.id:
                raise ValueError("question_id does not match the current question")
            if payload.action == "back":
                state.index = max(0, state.index - 1)
                state.updated_at = time.time()
                return self._response(state)

            values = self._validated_values(question, payload.values)
            state.answers[question.id] = values
            state.updated_at = time.time()
            if question.id == "symptoms" and EMERGENCY_VALUES.intersection(values):
                state.outcome = self._outcome(state, "emergency")
                return self._response(state)

            state.index += 1
            if state.index >= len(QUESTIONS):
                state.outcome = self._outcome(state, self._risk_level(state.answers))
            return self._response(state)

    @property
    def total_questions(self) -> int:
        return len(QUESTIONS)

    @staticmethod
    def _validated_values(
        question: TriageQuestion,
        values: list[str],
    ) -> list[str]:
        allowed = {option.value for option in question.options}
        selected = list(dict.fromkeys(value for value in values if value in allowed))
        if not selected:
            raise ValueError("at least one option is required")
        if not question.multiple and len(selected) != 1:
            raise ValueError("this question accepts exactly one option")
        if "none" in selected and len(selected) > 1:
            raise ValueError("'none' cannot be combined with other options")
        return selected

    @staticmethod
    def _risk_level(answers: dict[str, list[str]]) -> str:
        values = {
            value
            for question_values in answers.values()
            for value in question_values
        }
        if values.intersection(PROFESSIONAL_VALUES):
            return "professional_review"
        return "insufficient_information"

    def _outcome(self, state: TriageState, level: str) -> TriageOutcome:
        citations = self._citations_for_state(state)
        if level == "emergency":
            return TriageOutcome(
                level="emergency",
                title="存在需要优先处理的危险信号",
                summary=(
                    "您报告了活动性出血、消化道出血或急性神经系统症状之一。"
                    "这些症状不能通过维生素K自查判断原因，请立即联系急救服务"
                    "或尽快前往急诊。"
                ),
                recommendations=[
                    "不要等待线上问答结果，也不要自行服用维生素K试图止血。",
                    "如正在使用抗凝药，请携带药盒和近期INR结果就医。",
                    "如出现意识改变、呼吸困难或持续大量出血，请立即呼叫急救。",
                ],
                citations=citations,
            )
        if level == "professional_review":
            return TriageOutcome(
                level="professional_review",
                title="建议由医生或药师进一步评估",
                summary=(
                    "您的回答中包含可能影响维生素K需要量、吸收、利用或检测解释的因素。"
                    "仅凭问卷不能判断是否缺乏，也不能决定是否补充。"
                ),
                recommendations=[
                    "携带疾病史、用药清单、饮食情况和已有检测结果进行专业评估。",
                    "正在使用华法林或抗凝药时，不要自行增加或停用维生素K补充剂。",
                    "如需要检测，由医生结合INR、PIVKA-II、ucOC、dp-ucMGP或维生素K水平判断。",
                ],
                citations=citations,
            )
        return TriageOutcome(
            level="insufficient_information",
            title="当前信息不足以判断是否需要补充",
            summary=(
                "您没有报告明确的危险因素，但“没有报告症状或风险因素”不等于没有维生素K缺乏，"
                "也不能据此得出不需要补充的结论。"
            ),
            recommendations=[
                "优先通过日常饮食了解维生素K来源，不建议自行使用高剂量补充剂。",
                "如症状持续、饮食长期不足或存在肝胆、吸收不良和用药问题，请咨询医生或药师。",
                "是否缺乏以及是否需要补充应由专业评估和必要检测决定。",
            ],
            citations=citations,
        )

    def _citations_for_state(self, state: TriageState) -> list[Citation]:
        phrases = [
            "Vitamin K deficiency bleeding",
            "fat malabsorption vitamin K",
            "cholestasis vitamin K",
            "warfarin vitamin K INR",
            "green leafy vegetables phylloquinone",
            "PIVKA-II vitamin K status",
        ]
        evidence_ids = self.snapshot.metadata.search_evidence_phrases(
            phrases,
            limit=12,
            source_types={"literature", "structured"},
        )
        eligible = []
        for evidence in self.snapshot.metadata.get_evidence_many(evidence_ids):
            try:
                metadata = json.loads(evidence.get("metadata_json") or "{}")
            except (TypeError, ValueError):
                metadata = {}
            if (
                bool(evidence.get("answer_eligible", 1))
                and str(metadata.get("predicate") or "")
                not in METADATA_ONLY_ANSWER_PREDICATES
            ):
                eligible.append(evidence["id"])
        if not eligible:
            return []
        return self.engine._citations_for_claims(
            [
                Claim(
                    id=f"triage-claim-{uuid.uuid4().hex[:10]}",
                    text="维生素K风险自查一般证据",
                    evidence_ids=eligible[:5],
                )
            ]
        )

    @staticmethod
    def _response(state: TriageState) -> TriageSessionResponse:
        question = None
        status = "completed"
        if state.outcome is None:
            status = "in_progress"
            question = QUESTIONS[state.index]
        return TriageSessionResponse(
            session_id=state.session_id,
            status=status,
            progress=TriageProgress(
                current=min(state.index + 1, len(QUESTIONS)),
                total=len(QUESTIONS),
            ),
            question=question,
            answers=state.answers,
            outcome=state.outcome,
        )

    def _purge_expired(self) -> None:
        cutoff = time.time() - TRIAGE_TTL_SECONDS
        expired = [
            session_id
            for session_id, state in self._sessions.items()
            if state.updated_at < cutoff
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
