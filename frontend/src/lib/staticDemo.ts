import type {
  Answer,
  Citation,
  Claim,
  DataVersion,
  GraphMeta,
  GraphEdge,
  GraphNode,
  GraphPath,
  Health,
  SearchResult,
  Subgraph
} from "./types";

export const STATIC_DEMO_MODE = import.meta.env.VITE_STATIC_DEMO === "true";

interface StaticEvidence extends Citation {
  document_id: string;
  entity_ids: string[];
  predicate?: string;
  evidence_status?: string;
  graph_display_role?: string;
}

interface StaticData {
  version: DataVersion;
  nodes: GraphNode[];
  edges: GraphEdge[];
  evidence: StaticEvidence[];
}

let dataPromise: Promise<StaticData> | null = null;

function loadData(): Promise<StaticData> {
  if (!dataPromise) {
    dataPromise = fetch(`${import.meta.env.BASE_URL}real-evidence.json`).then((response) => {
      if (!response.ok) throw new Error(`静态知识库加载失败：${response.status}`);
      return response.json() as Promise<StaticData>;
    });
  }
  return dataPromise;
}

function normalize(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "")
    .replaceAll("维生素 k", "维生素k")
    .replaceAll("维他命k", "维生素k")
    .replaceAll("维k", "维生素k")
    .replaceAll("phylloquinone", "维生素k1")
    .replaceAll("menaquinone", "维生素k2")
    .replaceAll("inr", "国际标准化比值")
    .replaceAll("pt", "凝血酶原时间")
    .replaceAll("维生素k", "vitamink")
    .replaceAll("维他命k", "vitamink")
    .replaceAll("叶绿醌", "phylloquinone")
    .replaceAll("甲萘醌", "menaquinone")
    .replaceAll("华法林", "warfarin")
    .replaceAll("骨钙素", "osteocalcin")
    .replaceAll("胰岛素", "insulin")
    .replaceAll("血糖", "glucose")
    .replaceAll("维生素d", "vitamind")
    .replaceAll("基质gla蛋白", "matrixglaprotein")
    .replaceAll("异常凝血酶原", "pivkaii")
    .replaceAll("绿叶蔬菜", "greenleafyvegetables")
    .replaceAll("深绿色叶菜", "greenleafyvegetables");
}

function matchNodes(query: string, nodes: GraphNode[]): GraphNode[] {
  const normalized = normalize(query);
  const matches: Array<{ length: number; start: number; node: GraphNode }> = [];
  for (const node of nodes) {
    for (const alias of [node.name, node.id, ...node.aliases]) {
      const candidate = normalize(alias);
      if (!candidate) continue;
      let start = normalized.indexOf(candidate);
      while (start >= 0) {
        matches.push({ length: candidate.length, start, node });
        start = normalized.indexOf(candidate, start + 1);
      }
    }
  }
  matches.sort((left, right) => right.length - left.length || left.start - right.start);
  const output: GraphNode[] = [];
  const spans: Array<[number, number]> = [];
  for (const match of matches) {
    const end = match.start + match.length;
    if (spans.some(([start, existingEnd]) => match.start < existingEnd && end > start)) {
      continue;
    }
    if (!output.some((node) => node.id === match.node.id)) {
      output.push(match.node);
      spans.push([match.start, end]);
    }
    if (output.length >= 4) break;
  }
  return output;
}

const intentRules: Array<[string, string[]]> = [
  ["comparison", ["区别", "比较", "不同", "差异", "哪个好", "对比"]],
  ["food_sources", ["食物", "吃什么", "来源", "蔬菜", "叶菜", "纳豆", "饮食", "含有", "富含"]],
  ["drug_interactions", ["相互作用", "一起吃", "同服", "药物", "华法林", "抗凝", "抗生素"]],
  ["deficiency", ["缺乏", "不足", "缺什么", "风险人群", "谁会", "症状"]],
  ["functions", ["作用", "功能", "参与", "有什么好处", "影响什么", "机制", "凝血"]],
  ["lab_tests", ["检测", "检查", "化验", "指标", "评估", "测量", "反映"]],
  ["recommendations", ["建议", "推荐", "摄入量", "每天", "孕妇", "新生儿", "老人", "适用", "人群"]],
  ["research", ["研究", "RCT", "证据", "指南", "文献", "临床试验"]],
  ["definition", ["是什么", "什么是", "定义", "介绍", "介绍一下"]]
];

const predicatesByIntent: Record<string, Set<string>> = {
  functions: new Set(["SUPPORTS", "PARTICIPATES_IN", "ACTIVATES", "DISRUPTS", "CAN_CAUSE", "CAN_ALTER"]),
  food_sources: new Set(["CONTAINS", "RICH_IN", "MAY_CONTAIN", "RELATED_TO"]),
  drug_interactions: new Set([
    "INTERACTS_WITH",
    "INHIBITS",
    "CAN_ALTER",
    "CAN_CONTRIBUTE_TO",
    "ASSOCIATED_WITH",
    "REQUIRES_ASSESSMENT_FOR"
  ]),
  deficiency: new Set([
    "CAN_CAUSE",
    "CAN_CONTRIBUTE_TO",
    "AT_RISK",
    "DISRUPTS",
    "REQUIRES_ASSESSMENT_FOR"
  ]),
  lab_tests: new Set([
    "ASSESSES",
    "MAY_ASSESS",
    "MEASURES",
    "CONTRIBUTES_TO_ASSESSMENT",
    "MEASURES_IN_STUDY"
  ]),
  recommendations: new Set([
    "RECOMMENDED_FOR",
    "ADVICE",
    "GUIDES",
    "RECOMMENDS",
    "MAY_SUPPORT"
  ]),
  research: new Set(["HAS_OUTCOME", "STUDIES", "MEASURES_IN_STUDY", "RECOMMENDS"]),
  definition: new Set(["IS_FORM_OF", "SUPPORTS", "PARTICIPATES_IN", "CONTAINS", "RICH_IN"])
};

const relationTemplates: Record<string, string> = {
  IS_FORM_OF: "{source}是{target}的一种形式。",
  SUPPORTS: "{source}参与或支持{target}。",
  PARTICIPATES_IN: "{source}参与{target}。",
  ACTIVATES: "{source}参与{target}的活化或功能调节。",
  POTENTIALLY_PROTECTS_AGAINST: "知识库记录了{source}与{target}风险之间的关联，不能据此作出个体医疗结论。",
  MAY_CONTRIBUTE_TO: "{source}可能对{target}产生关联，解释时需考虑个体差异。",
  DISRUPTS: "{source}会干扰{target}。",
  CAN_CAUSE: "{source}可能导致或促成{target}。",
  CAN_CONTRIBUTE_TO: "{source}可能促成{target}。",
  AT_RISK: "{source}属于{target}相关风险需要关注的人群。",
  INHIBITS: "{source}可抑制{target}。",
  INCLUDES: "{source}包括{target}。",
  ASSOCIATED_WITH: "{source}与{target}存在关联，具体意义需结合监测和专业评估。",
  CAN_ALTER: "{source}可能改变{target}。",
  CONTAINS: "{source}含有{target}。",
  RICH_IN: "{source}可被视为富含{target}的食物类别之一。",
  MAY_CONTAIN: "{source}可能含有{target}，具体含量受加工与配方影响。",
  RECOMMENDED_FOR: "{source}与{target}相关的知识建议适用于该场景，实际执行应遵循专业指导。",
  ADVICE: "知识库将{source}与{target}建议关联起来。",
  ASSESSES: "{source}可用于评估{target}。",
  MAY_ASSESS: "{source}可作为研究与{target}相关的评估指标。",
  MEASURES: "{source}可用于测量或反映{target}。",
  CONTRIBUTES_TO_ASSESSMENT: "{source}是{target}评估的一个信息维度。",
  GUIDES: "{source}用于指导{target}。",
  TARGETS: "{source}以{target}为关注结局。",
  MAY_SUPPORT: "{source}可能支持{target}，但不能替代个体化治疗。",
  HAS_OUTCOME: "{source}记录了{target}这一研究结局。",
  STUDIES: "{source}研究了{target}。",
  RECOMMENDS: "{source}包含与{target}相关的推荐主题。",
  MEASURES_IN_STUDY: "{source}在研究中使用或测量{target}。",
  REQUIRES_ASSESSMENT_FOR: "{source}在{target}方面通常需要专业评估。",
  BELONGS_TO_TOPIC: "{source}归属于{target}相关主题。",
  RELATED_TO: "{source}与{target}存在知识库关联。",
  DEMO_RELATED_TO: "{source}与{target}是演示主题关联。"
};

function detectIntent(query: string): string {
  const scores = intentRules
    .map(([intent, keywords]) => [
      keywords.filter((keyword) => query.toLowerCase().includes(keyword.toLowerCase())).length,
      intent
    ] as const)
    .filter(([score]) => score > 0)
    .sort((left, right) => right[0] - left[0]);
  return scores[0]?.[1] ?? "general";
}

function isGeneralFollowup(query: string, entities: GraphNode[]): boolean {
  if (["天气", "火星", "手机", "考试", "满分", "治愈所有", "替代所有"].some((term) => query.includes(term))) {
    return false;
  }
  let residue = normalize(query);
  for (const entity of entities) {
    for (const alias of [entity.name, entity.id, ...entity.aliases]) {
      residue = residue.replaceAll(normalize(alias), "");
    }
  }
  return residue.replace(/[，。！？、,.!?和与及有什么关系统介绍一下的是]/g, "").length <= 4;
}

function safetyCheck(query: string): { notice: string; intent: string } | null {
  const compact = query.replace(/\s+/g, "");
  if (
    /(华法林|抗凝药).{0,20}(多少|几片|几粒|几毫克|剂量|毫克|mg)/i.test(compact) ||
    /(我|本人|患者|孩子|老人|孕妇).{0,16}(吃|服用|补充|摄入|用药).{0,16}(多少|几片|几粒|几毫克|剂量|毫克|mg)/i.test(
      compact
    ) ||
    /(怎么|可以|能|需要|想).{0,8}(停药|停用|换药|加量|减量)/i.test(compact)
  ) {
    return {
      notice:
        "涉及处方、停药或剂量调整的问题必须由医生或药师评估。本系统不能提供个体化用药决定。",
      intent: "medication"
    };
  }
  const rules: Array<[string[], string, string]> = [
    [
      ["出血不止", "止不住血", "大量出血", "黑便", "血便", "呕血", "严重头痛", "呼吸困难"],
      "这可能属于需要紧急处理的症状。请立即联系急救服务或尽快前往急诊，不要等待线上问答结果。",
      "emergency"
    ],
    [
      ["给我开药", "怎么停药", "自己停药", "华法林吃多少", "抗凝药剂量", "具体剂量"],
      "涉及处方、停药或剂量调整的问题必须由医生或药师评估。本系统不能提供个体化用药决定。",
      "medication"
    ],
    [
      ["我得了什么病", "帮我诊断", "是否患病", "确诊"],
      "本系统不能进行疾病诊断。请携带症状、检验结果和用药信息咨询专业医疗人员。",
      "diagnosis"
    ]
  ];
  for (const [terms, notice, intent] of rules) {
    if (terms.some((term) => compact.includes(term))) return { notice, intent };
  }
  return null;
}

function graphPaths(
  sourceId: string,
  targetId: string,
  nodes: GraphNode[],
  edges: GraphEdge[],
  maxHops = 2,
  limit = 3
): GraphPath[] {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const adjacency = new Map<string, Array<{ edge: GraphEdge; neighbor: string }>>();
  for (const edge of edges) {
    adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), { edge, neighbor: edge.target }]);
    adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), { edge, neighbor: edge.source }]);
  }
  const queue: Array<{ current: string; nodes: GraphNode[]; edges: GraphEdge[] }> = [];
  const source = nodeById.get(sourceId);
  if (!source) return [];
  queue.push({ current: sourceId, nodes: [source], edges: [] });
  const output: GraphPath[] = [];
  while (queue.length && output.length < limit) {
    const item = queue.shift()!;
    if (item.edges.length >= maxHops) continue;
    for (const { edge, neighbor: neighborId } of adjacency.get(item.current) ?? []) {
      if (item.nodes.some((node) => node.id === neighborId)) continue;
      const neighbor = nodeById.get(neighborId);
      if (!neighbor) continue;
      const pathNodes = [...item.nodes, neighbor];
      const pathEdges = [...item.edges, edge];
      if (neighborId === targetId) {
        output.push({
          nodes: pathNodes,
          edges: pathEdges,
          evidence_ids: [...new Set(pathEdges.flatMap((pathEdge) => pathEdge.evidence_ids))]
        });
        if (output.length >= limit) break;
      } else {
        queue.push({ current: neighborId, nodes: pathNodes, edges: pathEdges });
      }
    }
  }
  return output;
}

function relatedFacts(
  entity: GraphNode,
  intent: string,
  data: StaticData
): Array<{ edge: GraphEdge; neighbor: GraphNode }> {
  const nodeById = new Map(data.nodes.map((node) => [node.id, node]));
  const predicates = predicatesByIntent[intent];
  return data.edges
    .filter((edge) => edge.source === entity.id || edge.target === entity.id)
    .map((edge) => ({
      edge,
      neighbor: nodeById.get(edge.source === entity.id ? edge.target : edge.source)
    }))
    .filter(
      (item): item is { edge: GraphEdge; neighbor: GraphNode } =>
        Boolean(item.neighbor) && (!predicates || predicates.has(item.edge.predicate))
    )
    .sort((left, right) => right.edge.confidence - left.edge.confidence);
}

function claimText(edge: GraphEdge, source?: GraphNode, target?: GraphNode): string {
  if (!source || !target) return "";
  const template = relationTemplates[edge.predicate] ?? `${source.name}与${target.name}存在知识库关联。`;
  return template.replaceAll("{source}", source.name).replaceAll("{target}", target.name);
}

function heading(intent: string, nodes: GraphNode[]): string {
  const subject = nodes.slice(0, 2).map((node) => node.name).join("、") || "该问题";
  const values: Record<string, string> = {
    food_sources: `知识库中与${subject}相关的食物来源如下：`,
    drug_interactions: `知识库中与${subject}相关的药物相互作用线索如下：`,
    deficiency: `知识库中与${subject}相关的缺乏和风险信息如下：`,
    functions: `知识库中与${subject}相关的功能信息如下：`,
    lab_tests: `知识库中与${subject}相关的检测信息如下：`,
    recommendations: `知识库中与${subject}相关的建议信息如下：`,
    research: `知识库中与${subject}相关的研究证据信息如下：`,
    comparison: `知识库中关于${subject}的关系路径如下：`,
    definition: `知识库中关于${subject}的结构化信息如下：`
  };
  return values[intent] ?? `知识库中与${subject}相关的证据如下：`;
}

export async function getStaticHealth(): Promise<Health> {
  const data = await loadData();
  return {
    status: "ok",
    runtime_llm: false,
    data_version: data.version,
    graph_backend: "browser-static",
    vector_backend: "browser-static",
    metadata_backend: "demo-data.json"
  };
}

export async function getStaticGraphMeta(): Promise<GraphMeta> {
  const data = await loadData();
  return {
    domains: [...new Set(data.nodes.map((node) => node.domain))].sort(),
    types: [...new Set(data.nodes.map((node) => node.type))].sort(),
    stats: { nodes: data.nodes.length, edges: data.edges.length },
    data_version: data.version
  };
}

export async function searchStaticGraph(
  query: string
): Promise<{ items: GraphNode[]; total: number }> {
  const data = await loadData();
  const normalized = normalize(query);
  const items = data.nodes
    .filter((node) =>
      [node.name, node.id, ...node.aliases].some((value) =>
        normalize(value).includes(normalized)
      )
    )
    .slice(0, 30);
  return { items, total: items.length };
}

export async function getStaticSubgraph(
  entityIds: string[],
  depth: number,
  domains: string[]
): Promise<Subgraph> {
  const data = await loadData();
  const nodeById = new Map(data.nodes.map((node) => [node.id, node]));
  const selected = new Set(entityIds);
  let frontier = [...entityIds];
  const selectedEdges = new Map<string, GraphEdge>();
  for (let hop = 0; hop < depth; hop += 1) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const edge of data.edges) {
        if (edge.source !== id && edge.target !== id) continue;
        const neighborId = edge.source === id ? edge.target : edge.source;
        const neighbor = nodeById.get(neighborId);
        if (!neighbor || (domains.length && !domains.includes(neighbor.domain))) continue;
        selectedEdges.set(edge.id, edge);
        if (!selected.has(neighborId) && selected.size < 100) {
          selected.add(neighborId);
          next.push(neighborId);
        }
      }
    }
    frontier = next;
  }
  return {
    nodes: [...selected].map((id) => nodeById.get(id)).filter((node): node is GraphNode => Boolean(node)),
    edges: [...selectedEdges.values()].filter(
      (edge) => selected.has(edge.source) && selected.has(edge.target)
    ),
    data_version: data.version
  };
}

export async function searchStaticEvidence(query: string): Promise<{
  items: SearchResult[];
  total: number;
}> {
  const data = await loadData();
  const nodeById = new Map(data.nodes.map((node) => [node.id, node]));
  const terms = [
    ...new Set([
      ...normalize(query)
        .split(/[，。！？、,.!?和与及]/)
        .filter((term) => term.length > 0),
      ...semanticTerms(query)
    ])
  ];
  const items = data.evidence
    .map((item) => {
      const entities = item.entity_ids
        .map((entityId) => nodeById.get(entityId))
        .filter((node): node is GraphNode => Boolean(node));
      const haystack = normalize(
        `${item.source_title} ${item.snippet} ${item.publisher} ${item.predicate ?? ""} ` +
          entities.flatMap((node) => [node.name, ...node.aliases]).join(" ")
      );
      const score = terms.length
        ? terms.filter((term) => haystack.includes(term)).length / terms.length
        : 0;
      return {
        chunk_id: item.document_id,
        document_id: item.document_id,
        source_id: item.source_id,
        title: item.source_title,
        source_classification: item.source_classification,
        data_origin: item.data_origin,
        data_owner: item.data_owner,
        access_scope: item.access_scope,
        source_type: item.source_type,
        review_status: item.review_status ?? "accepted",
        input_status: item.input_status ?? "adopted",
        fusion_status: item.fusion_status ?? "accepted",
        evidence_status: item.evidence_status ?? "",
        graph_display_role: item.graph_display_role ?? "",
        answer_eligible: item.answer_eligible ?? true,
        source_record_id: item.source_id,
        source_version: item.source_version ?? "",
        source_locator: item.source_locator ?? item.locator,
        snippet: item.snippet,
        entity_ids: item.entity_ids,
        score,
        is_demo: item.is_demo
      } satisfies SearchResult;
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 20);
  return { items, total: items.length };
}

const PREDICATE_LABELS: Record<string, string> = {
  contains: "含有/存在于",
  is_antagonized_by: "受到拮抗/存在拮抗关系",
  deficiency_causes: "缺乏可导致",
  excess_causes: "过量可导致",
  regulates_expression_of: "调节表达",
  activates_protein: "参与或激活蛋白功能",
  has_outcome_biomarker: "关联结局指标",
  indicates_risk_of: "提示风险",
  cross_sectionally_associated_with: "存在横断面关联",
  participates_in_cycle: "参与循环",
  is_carboxylated_by: "参与羧化",
  measured_by: "通过该指标测量",
  reflects_status_of: "反映状态",
  is_synthesized_by: "合成来源",
  targets_tissue: "作用于组织",
  prevents: "预防",
  increases: "增加",
  reduces: "降低",
  affects: "影响",
  has_subject: "研究对象或人群",
  requires: "需要",
  supported_by: "研究类型支持",
  has_exposure_intervention: "暴露或干预",
  has_exposure_dose_record: "暴露剂量记录",
  measured_vitamin_k_form: "测量维生素K形式"
};

const SEMANTIC_EXPANSIONS: Array<[string, string[]]> = [
  ["食物", ["food", "diet", "vegetable", "leafy", "oil", "source", "intake"]],
  ["来源", ["food", "diet", "vegetable", "leafy", "oil", "source"]],
  ["饮食", ["diet", "food", "intake"]],
  ["华法林", ["warfarin", "antagonist", "anticoagulant"]],
  ["抗凝", ["anticoagulant", "warfarin", "antagonist"]],
  ["缺乏", ["deficiency", "deficient", "absence", "bleeding", "causes"]],
  ["风险", ["risk", "bleeding", "deficiency", "association"]],
  ["骨", ["bone", "osteocalcin", "carboxylation", "fracture"]],
  ["骨钙素", ["osteocalcin", "carboxylation", "ucoc"]],
  ["血管", ["vascular", "artery", "calcification"]],
  ["钙化", ["calcification", "matrix gla", "mgp"]],
  ["检测", ["plasma", "serum", "measure", "biomarker", "assay"]],
  ["指标", ["biomarker", "plasma", "serum", "measure"]],
  ["新生儿", ["infant", "newborn", "neonatal", "birth"]],
  ["孕妇", ["pregnan", "gestation", "maternal"]],
  ["儿童", ["children", "child", "pediatric"]],
  ["老年人", ["older", "elderly", "aged"]],
  ["功能", ["function", "cofactor", "protein", "role", "participates"]],
  ["形式", ["form", "phylloquinone", "menaquinone", "mk-"]],
  ["区别", ["phylloquinone", "menaquinone", "form", "vitamin k1", "vitamin k2"]],
  ["研究", ["study", "trial", "randomized", "cohort"]],
  ["指南", ["guideline", "recommendation", "consensus"]]
];

function predicateLabel(predicate: string): string {
  return PREDICATE_LABELS[predicate] ?? `“${predicate}”关系`;
}

function evidenceHaystack(item: StaticEvidence): string {
  return normalize(
    [
      item.source_title,
      item.publisher,
      item.snippet,
      item.locator,
      item.predicate ?? "",
      item.review_status ?? ""
    ].join(" ")
  );
}

function semanticTerms(query: string): string[] {
  const normalizedQuery = normalize(query);
  const output = new Set<string>();
  for (const [trigger, terms] of SEMANTIC_EXPANSIONS) {
    if (normalizedQuery.includes(normalize(trigger))) {
      for (const term of terms) output.add(term);
    }
  }
  for (const term of normalizedQuery.match(/[a-z][a-z0-9-]{2,}/g) ?? []) {
    output.add(term);
  }
  return [...output];
}

function rankRealEvidence(
  query: string,
  entities: GraphNode[],
  intent: string,
  data: StaticData
): StaticEvidence[] {
  const terms = semanticTerms(query);
  const intentTerms = semanticTerms(intent === "food_sources" ? "食物来源" : query);
  const ranked: Array<{ item: StaticEvidence; score: number; matchedEntities: number }> = [];

  for (const item of data.evidence) {
    if (item.answer_eligible === false || item.snippet.trim().length < 20) continue;
    const haystack = evidenceHaystack(item);
    let score = 0;

    const directMatches = entities.filter((node) => item.entity_ids.includes(node.id));
    const textMatches = entities.filter(
      (node) =>
        !directMatches.includes(node) &&
        (haystack.includes(normalize(node.name)) ||
          node.aliases.some((alias) => haystack.includes(normalize(alias))))
    );
    score += directMatches.length * 10 + textMatches.length * 2;
    if (directMatches.length >= 2) score += 10;

    for (const term of terms) {
      if (haystack.includes(normalize(term))) score += 2.5;
    }
    if (intent === "food_sources") {
      if (["contains", "is_synthesized_by"].includes(item.predicate ?? "")) score += 8;
      if (["food", "diet", "vegetable", "leafy", "oil"].some((term) => haystack.includes(term))) {
        score += 5;
      }
    }
    if (intent === "drug_interactions" && haystack.includes("warfarin")) score += 6;
    if (intent === "deficiency" && haystack.includes("deficiency")) score += 5;
    if (intent === "lab_tests" && ["measured_by", "reflects_status_of", "has_outcome_biomarker"].includes(item.predicate ?? "")) {
      score += 5;
    }
    if (intent === "research" && ["trial", "study", "randomized", "cohort"].some((term) => haystack.includes(term))) {
      score += 4;
    }
    if (intent === "definition" && ["cofactor", "fat-soluble", "form", "protein"].some((term) => haystack.includes(term))) {
      score += 3;
    }
    for (const term of intentTerms) {
      if (haystack.includes(normalize(term))) score += 1.5;
    }
    if (item.evidence_level === "A") score += 2;
    if (item.review_status === "accepted") score += 1;
    if (score > 0) {
      ranked.push({ item, score, matchedEntities: directMatches.length });
    }
  }

  ranked.sort(
    (left, right) =>
      right.score - left.score ||
      Number(right.item.evidence_level === "A") - Number(left.item.evidence_level === "A")
  );
  const minimumScore = entities.length ? 8 : 6;
  const pairMatches = ranked.filter((item) => item.matchedEntities >= 2);
  const candidates = entities.length >= 2 && pairMatches.length >= 1 ? pairMatches : ranked;
  const selected: StaticEvidence[] = [];
  const seen = new Set<string>();
  for (const { item, score } of candidates) {
    if (score < minimumScore) continue;
    const key = `${item.predicate ?? ""}:${item.snippet.slice(0, 140).toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    selected.push(item);
    if (selected.length >= 5) break;
  }
  return selected;
}

function firstMatchingEvidence(
  data: StaticData,
  patterns: RegExp[],
  usedSources: Set<string>
): StaticEvidence | undefined {
  const candidates = data.evidence
    .filter((item) => item.answer_eligible !== false)
    .sort(
      (left, right) =>
        Number(right.evidence_level === "A") - Number(left.evidence_level === "A")
    );
  for (const pattern of patterns) {
    const match = candidates.find((item) => {
      if (usedSources.has(item.source_id)) return false;
      const text = `${item.snippet} ${item.locator}`;
      return pattern.test(text);
    });
    if (match) return match;
  }
  return undefined;
}

function warfarinVitaminKAnswer(
  query: string,
  data: StaticData,
  entities: GraphNode[],
  intent: string,
  sessionId: string,
  started: number
): Answer | null {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery.includes("warfarin") || !normalizedQuery.includes("vitamink")) {
    return null;
  }

  const usedSources = new Set<string>();
  const mechanism = firstMatchingEvidence(
    data,
    [
      /VKORC1 inhibitor.*reduced Vitamin K/i,
      /Vitamin K epoxide reductase.*Vitamin K hydroquinone/i,
      /By targeting VKOR.*coagulation proteins/i
    ],
    usedSources
  );
  if (mechanism) usedSources.add(mechanism.source_id);
  const foodEffect = firstMatchingEvidence(
    data,
    [/large amounts of Vitamin K.*lower the INR/i, /dark green leafy vegetables.*INR/i],
    usedSources
  );
  if (foodEffect) usedSources.add(foodEffect.source_id);
  const reversal = firstMatchingEvidence(
    data,
    [/low-dose Vitamin K.*managed/i, /phytonadione.*excessive anticoagulation/i],
    usedSources
  );
  if (reversal) usedSources.add(reversal.source_id);
  const monitoring = firstMatchingEvidence(
    data,
    [/coagulation monitoring/i, /monitoring.*INR/i, /monitor.*INR/i],
    usedSources
  );

  const selected = [mechanism, foodEffect, reversal, monitoring].filter(
    (item): item is StaticEvidence => Boolean(item)
  );
  if (!mechanism || selected.length < 3) return null;

  const claims: Claim[] = [];
  function addClaim(text: string, items: Array<StaticEvidence | undefined>) {
    const ids = items.filter((item): item is StaticEvidence => Boolean(item)).map((item) => item.id);
    if (!ids.length) return;
    claims.push({
      id: `static-claim-${claims.length}`,
      text,
      evidence_ids: ids,
      relation: "warfarin_vitamin_k_synthesis"
    });
  }

  addClaim(
    "华法林通过抑制 VKORC1，阻断维生素 K 环氧化物还原，减少活性维生素 K 的再生，并影响维生素 K 依赖凝血因子的活化。",
    [mechanism]
  );
  addClaim(
    "两者是明确的药理学拮抗关系：维生素 K 摄入或补充会影响华法林的抗凝强度，需要结合 INR 和用药情况管理。",
    [foodEffect, reversal]
  );
  if (foodEffect) {
    addClaim(
      "富含维生素 K 的食物，例如菠菜、羽衣甘蓝等深绿色叶菜，可能降低 INR。",
      [foodEffect]
    );
  }
  if (reversal) {
    addClaim(
      "华法林抗凝过度时，维生素 K 可在专业评估下用于纠正凝血状态，具体处理取决于 INR、出血情况和临床背景。",
      [reversal]
    );
  }
  if (monitoring) {
    addClaim(
      "华法林使用期间需要按医嘱监测 INR，并尽量保持日常维生素 K 摄入相对稳定，不应自行改变补充剂或摄入量。",
      [monitoring]
    );
  }

  const edgeById = new Map(data.edges.map((edge) => [edge.id, edge]));
  const nodeById = new Map(data.nodes.map((node) => [node.id, node]));
  const paths: GraphPath[] = [];
  for (const item of selected) {
    const edge = edgeById.get(item.id);
    const source = edge ? nodeById.get(edge.source) : undefined;
    const target = edge ? nodeById.get(edge.target) : undefined;
    if (edge && source && target) {
      paths.push({ nodes: [source, target], edges: [edge], evidence_ids: [item.id] });
    }
  }
  const citationIds = [...new Set(claims.flatMap((claim) => claim.evidence_ids))];
  const citations = citationIds
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is StaticEvidence => Boolean(item));

  return {
    session_id: sessionId,
    query,
    normalized_query: normalizedQuery,
    intent,
    answer_text:
      "华法林与维生素 K 属于明确的药理学拮抗关系，需要结合机制、饮食和 INR 监测理解。\n\n" +
      claims.map((claim) => `- ${claim.text}`).join("\n") +
      "\n\n以上结论由真实外部文献证据合成，具体剂量调整、停药或抗凝过度处理必须由医生或药师评估。",
    claims,
    citations,
    graph_paths: paths,
    sufficiency: "sufficient",
    safety_notice: null,
    related_entities: entities,
    data_version: data.version,
    elapsed_ms: Math.round(performance.now() - started)
  };
}

export async function askStaticQuestion(query: string): Promise<Answer> {
  const started = performance.now();
  const data = await loadData();
  const nodeById = new Map(data.nodes.map((node) => [node.id, node]));
  const evidenceById = new Map(data.evidence.map((item) => [item.id, item]));
  const sessionId = `static-${crypto.randomUUID()}`;
  const safety = safetyCheck(query);
  if (safety) {
    return {
      session_id: sessionId,
      query,
      normalized_query: normalize(query),
      intent: safety.intent,
      answer_text: safety.notice,
      claims: [],
      citations: [],
      graph_paths: [],
      sufficiency: "none",
      safety_notice: safety.notice,
      related_entities: [],
      data_version: data.version,
      elapsed_ms: Math.round(performance.now() - started)
    };
  }

  const entities = matchNodes(query, data.nodes);
  const intent = detectIntent(query);
  const synthesized = warfarinVitaminKAnswer(
    query,
    data,
    entities,
    intent,
    sessionId,
    started
  );
  if (synthesized) return synthesized;
  const selectedEvidence = rankRealEvidence(query, entities, intent, data);
  const edgeById = new Map(data.edges.map((edge) => [edge.id, edge]));
  const claims: Claim[] = [];
  const seen = new Set<string>();
  const paths: GraphPath[] = [];
  for (const evidence of selectedEvidence) {
    const edge = edgeById.get(evidence.id);
    if (!edge) continue;
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) continue;
    const text = `真实文献抽取关系：${source.name} — ${predicateLabel(edge.predicate)} → ${target.name}。`;
    if (seen.has(text)) continue;
    seen.add(text);
    claims.push({
      id: `static-claim-${claims.length}`,
      text,
      evidence_ids: [evidence.id],
      relation: edge.predicate
    });
    paths.push({
      nodes: [source, target],
      edges: [edge],
      evidence_ids: [evidence.id]
    });
  }

  if (claims.length) {
    const citationIds = [...new Set(claims.flatMap((claim) => claim.evidence_ids))];
    const citations = citationIds
      .map((id) => evidenceById.get(id))
      .filter((item): item is StaticEvidence => Boolean(item));
    const sourceCount = new Set(citations.map((item) => item.source_id)).size;
    const caution =
      "\n\n以上内容是对真实外部文献三元组和原文片段的检索式整理，不构成诊断、处方或个体化用药建议。";
    return {
      session_id: sessionId,
      query,
      normalized_query: normalize(query),
      intent,
      answer_text:
        `在真实外部文献证据中检索到 ${claims.length} 条已审核记录（涉及 ${sourceCount} 个来源）：\n\n` +
        claims.map((claim) => `- ${claim.text}`).join("\n") +
        "\n\n右侧证据卡保留了 PMID、原文片段、证据等级和 `external/public` 来源标签。" +
        caution,
      claims,
      citations,
      graph_paths: paths,
      sufficiency: claims.length >= 2 ? "sufficient" : "partial",
      safety_notice: null,
      related_entities: entities,
      data_version: data.version,
      elapsed_ms: Math.round(performance.now() - started)
    };
  }

  const related = entities.length
    ? entities
    : data.nodes.filter((node) => normalize(query).includes(normalize(node.name))).slice(0, 6);
  return {
    session_id: sessionId,
    query,
    normalized_query: normalize(query),
    intent,
    answer_text:
      "当前已审核真实外部文献证据中没有找到足够直接依据。系统不会使用生成模型补写医学结论，也不会把待审核证据用于正式回答。",
    claims: [],
    citations: [],
    graph_paths: [],
    sufficiency: "none",
    safety_notice: null,
    related_entities: related,
    data_version: data.version,
    elapsed_ms: Math.round(performance.now() - started)
  };
}
