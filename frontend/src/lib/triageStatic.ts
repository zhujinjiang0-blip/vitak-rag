import { searchStaticEvidence } from "./staticDemo";
import type {
  Citation,
  TriageOutcome,
  TriageQuestion,
  TriageSession
} from "./types";

interface StaticTriageState {
  sessionId: string;
  index: number;
  answers: Record<string, string[]>;
  outcome: TriageOutcome | null;
  updatedAt: number;
}

const QUESTIONS: TriageQuestion[] = [
  {
    id: "symptoms",
    prompt: "最近是否出现以下需要优先处理的情况？",
    help_text: "可以选择多项。如存在活动性出血或急性神经系统症状，请优先就医。",
    multiple: true,
    options: [
      {
        value: "active_bleeding",
        label: "持续或不明原因出血",
        description: "例如伤口持续渗血、鼻血难以停止"
      },
      {
        value: "black_stool",
        label: "黑便、血便或呕血",
        description: "可能需要紧急评估"
      },
      {
        value: "severe_headache",
        label: "严重头痛或急性神经系统症状",
        description: "包括突发剧烈头痛、意识异常"
      },
      { value: "none", label: "以上都没有", description: "" },
      { value: "unsure", label: "不确定", description: "无法判断时按需专业评估处理" }
    ]
  },
  {
    id: "conditions",
    prompt: "是否有医生诊断过影响维生素K吸收或利用的情况？",
    help_text: "不需要填写具体病名，可多选。",
    multiple: true,
    options: [
      { value: "fat_malabsorption", label: "脂肪吸收不良", description: "" },
      { value: "cholestasis_liver", label: "胆汁淤积或肝胆疾病", description: "" },
      { value: "gi_surgery", label: "胃肠道手术或短肠情况", description: "" },
      { value: "none", label: "没有", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  },
  {
    id: "medications",
    prompt: "是否正在使用以下药物？",
    help_text: "仅用于判断是否需要专业评估，不会生成剂量建议。",
    multiple: true,
    options: [
      { value: "warfarin", label: "华法林或其他抗凝药", description: "" },
      { value: "long_antibiotics", label: "长期抗生素", description: "" },
      { value: "other_long_term_medication", label: "其他长期药物", description: "" },
      { value: "none", label: "没有", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  },
  {
    id: "special_population",
    prompt: "这个问题是否涉及以下人群？",
    help_text: "",
    multiple: true,
    options: [
      { value: "newborn", label: "新生儿", description: "" },
      { value: "pregnancy", label: "孕期", description: "" },
      { value: "breastfeeding", label: "哺乳期", description: "" },
      { value: "none", label: "都不涉及", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  },
  {
    id: "diet",
    prompt: "最近的饮食中，深绿色叶菜、植物油或发酵豆制品摄入如何？",
    help_text: "这里仅做膳食背景了解，不据此诊断缺乏。",
    multiple: false,
    options: [
      { value: "very_low_green_vegetables", label: "长期很少摄入", description: "" },
      { value: "prolonged_low_intake", label: "整体进食量长期不足", description: "" },
      { value: "normal", label: "基本正常", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  },
  {
    id: "labs",
    prompt: "是否已有与维生素K相关的检测结果？",
    help_text: "包括 INR、PIVKA-II、ucOC、dp-ucMGP 或维生素K水平。",
    multiple: false,
    options: [
      { value: "abnormal_vitamin_k_lab", label: "有，结果异常", description: "" },
      { value: "abnormal_inr", label: "有，INR异常", description: "" },
      { value: "normal", label: "有，结果正常", description: "" },
      { value: "none", label: "没有检测", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  },
  {
    id: "supplement",
    prompt: "目前是否正在补充维生素K？",
    help_text: "系统不会根据该回答调整或停止任何补充方案。",
    multiple: false,
    options: [
      { value: "regular", label: "规律补充", description: "" },
      { value: "occasional", label: "偶尔补充", description: "" },
      { value: "none", label: "没有补充", description: "" },
      { value: "unsure", label: "不确定", description: "" }
    ]
  }
];

const EMERGENCY_VALUES = new Set([
  "active_bleeding",
  "black_stool",
  "severe_headache"
]);
const PROFESSIONAL_VALUES = new Set([
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
  "unsure"
]);
const sessions = new Map<string, StaticTriageState>();

export function startStaticTriage(): Promise<TriageSession> {
  const sessionId = `triage-static-${crypto.randomUUID()}`;
  const state: StaticTriageState = {
    sessionId,
    index: 0,
    answers: {},
    outcome: null,
    updatedAt: Date.now()
  };
  sessions.set(sessionId, state);
  return Promise.resolve(toSession(state));
}

export function getStaticTriageSession(
  sessionId: string
): Promise<TriageSession> {
  const state = sessions.get(sessionId);
  if (!state) return Promise.reject(new Error("自查会话不存在或已过期"));
  return Promise.resolve(toSession(state));
}

export async function answerStaticTriage(
  sessionId: string,
  questionId: string,
  values: string[],
  action: "next" | "back" = "next"
): Promise<TriageSession> {
  const state = sessions.get(sessionId);
  if (!state) throw new Error("自查会话不存在或已过期");
  if (state.outcome) return toSession(state);
  const question = QUESTIONS[state.index];
  if (questionId !== question.id) throw new Error("当前问题已变化，请重新加载");
  if (action === "back") {
    state.index = Math.max(0, state.index - 1);
    state.updatedAt = Date.now();
    return toSession(state);
  }
  validateValues(question, values);
  state.answers[question.id] = [...values];
  state.updatedAt = Date.now();
  if (question.id === "symptoms" && values.some((value) => EMERGENCY_VALUES.has(value))) {
    state.outcome = await buildOutcome("emergency");
    return toSession(state);
  }
  state.index += 1;
  if (state.index >= QUESTIONS.length) {
    const allValues = new Set(Object.values(state.answers).flat());
    state.outcome = await buildOutcome(
      [...allValues].some((value) => PROFESSIONAL_VALUES.has(value))
        ? "professional_review"
        : "insufficient_information"
    );
  }
  return toSession(state);
}

function validateValues(question: TriageQuestion, values: string[]) {
  const allowed = new Set(question.options.map((option) => option.value));
  if (!values.length || values.some((value) => !allowed.has(value))) {
    throw new Error("请选择有效选项");
  }
  if (!question.multiple && values.length !== 1) {
    throw new Error("该问题只能选择一项");
  }
  if (values.includes("none") && values.length > 1) {
    throw new Error("“没有”不能与其他选项同时选择");
  }
}

function toSession(state: StaticTriageState): TriageSession {
  return {
    session_id: state.sessionId,
    status: state.outcome ? "completed" : "in_progress",
    progress: {
      current: Math.min(state.index + 1, QUESTIONS.length),
      total: QUESTIONS.length
    },
    question: state.outcome ? null : QUESTIONS[state.index],
    answers: state.answers,
    outcome: state.outcome
  };
}

async function buildOutcome(level: TriageOutcome["level"]): Promise<TriageOutcome> {
  const citations = await generalCitations();
  if (level === "emergency") {
    return {
      level,
      title: "存在需要优先处理的危险信号",
      summary:
        "您报告了活动性出血、消化道出血或急性神经系统症状之一。这些症状不能通过维生素K自查判断原因，请立即联系急救服务或尽快前往急诊。",
      recommendations: [
        "不要等待线上问答结果，也不要自行服用维生素K试图止血。",
        "如正在使用抗凝药，请携带药盒和近期INR结果就医。",
        "如出现意识改变、呼吸困难或持续大量出血，请立即呼叫急救。"
      ],
      citations,
      cannot_conclude:
        "该自查不能诊断维生素K缺乏，也不能判断个人是否需要补充或确定剂量。"
    };
  }
  if (level === "professional_review") {
    return {
      level,
      title: "建议由医生或药师进一步评估",
      summary:
        "您的回答中包含可能影响维生素K需要量、吸收、利用或检测解释的因素。仅凭问卷不能判断是否缺乏，也不能决定是否补充。",
      recommendations: [
        "携带疾病史、用药清单、饮食情况和已有检测结果进行专业评估。",
        "正在使用华法林或抗凝药时，不要自行增加或停用维生素K补充剂。",
        "如需要检测，由医生结合INR、PIVKA-II、ucOC、dp-ucMGP或维生素K水平判断。"
      ],
      citations,
      cannot_conclude:
        "该自查不能诊断维生素K缺乏，也不能判断个人是否需要补充或确定剂量。"
    };
  }
  return {
    level: "insufficient_information",
    title: "当前信息不足以判断是否需要补充",
    summary:
      "您没有报告明确的危险因素，但“没有报告症状或风险因素”不等于没有维生素K缺乏，也不能据此得出不需要补充的结论。",
    recommendations: [
      "优先通过日常饮食了解维生素K来源，不建议自行使用高剂量补充剂。",
      "如症状持续、饮食长期不足或存在肝胆、吸收不良和用药问题，请咨询医生或药师。",
      "是否缺乏以及是否需要补充应由专业评估和必要检测决定。"
    ],
    citations,
    cannot_conclude:
      "该自查不能诊断维生素K缺乏，也不能判断个人是否需要补充或确定剂量。"
  };
}

async function generalCitations(): Promise<Citation[]> {
  const result = await searchStaticEvidence("维生素K缺乏 凝血 膳食来源");
  return result.items.slice(0, 4).map((item) => ({
    id: item.chunk_id,
    source_id: item.source_id,
    source_title: item.title,
    source_type: item.source_type,
    source_classification: item.source_classification,
    data_origin: item.data_origin,
    data_owner: item.data_owner,
    access_scope: item.access_scope,
    publisher: "",
    published_at: "",
    url: item.url,
    evidence_level: item.evidence_level ?? "not_scored",
    locator: item.source_locator,
    snippet: item.snippet,
    is_demo: item.is_demo,
    review_status: item.review_status,
    input_status: item.input_status,
    fusion_status: item.fusion_status,
    evidence_status: item.evidence_status,
    source_version: item.source_version,
    source_locator: item.source_locator
  }));
}
