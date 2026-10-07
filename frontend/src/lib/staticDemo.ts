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
    dataPromise = fetch(`${import.meta.env.BASE_URL}demo-data.json`).then((response) => {
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
    .replaceAll("pt", "凝血酶原时间");
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
  const terms = normalize(query)
    .split(/[，。！？、,.!?和与及]/)
    .filter((term) => term.length > 0);
  const items = data.evidence
    .map((item) => {
      const haystack = normalize(`${item.source_title}${item.snippet}${item.publisher}`);
      const score = terms.length
        ? terms.filter((term) => haystack.includes(term)).length / terms.length
        : 0;
      return {
        chunk_id: item.document_id,
        document_id: item.document_id,
        source_id: item.source_id,
        title: item.source_title,
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

  let entities = matchNodes(query, data.nodes);
  const intent = detectIntent(query);
  const generalAllowed = intent !== "general" || isGeneralFollowup(query, entities);
  let paths: GraphPath[] = [];
  if (entities.length >= 2) {
    paths = graphPaths(entities[0].id, entities[1].id, data.nodes, data.edges);
  }

  const facts =
    generalAllowed && entities.length === 1 && paths.length === 0
      ? relatedFacts(entities[0], intent, data)
      : [];

  const selectedEdges: GraphEdge[] = paths.length
    ? paths.flatMap((path) => path.edges)
    : facts.slice(0, 8).map((fact) => fact.edge);
  const claims: Claim[] = [];
  const seen = new Set<string>();
  for (const edge of selectedEdges) {
    if (!edge.evidence_ids.length) continue;
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    const text = claimText(edge, source, target);
    if (!text || seen.has(text)) continue;
    seen.add(text);
    claims.push({
      id: `static-claim-${claims.length}`,
      text,
      evidence_ids: edge.evidence_ids.slice(0, 3),
      relation: edge.predicate
    });
    if (claims.length >= 8) break;
  }

  if (claims.length) {
    const directPaths = paths.length
      ? paths
      : facts.slice(0, 6).flatMap((fact) => {
          const source = nodeById.get(fact.edge.source);
          const target = nodeById.get(fact.edge.target);
          return source && target
            ? [{ nodes: [source, target], edges: [fact.edge], evidence_ids: fact.edge.evidence_ids }]
            : [];
        });
    const citationIds = [...new Set(claims.flatMap((claim) => claim.evidence_ids))];
    const citations = citationIds
      .map((id) => evidenceById.get(id))
      .filter((item): item is StaticEvidence => Boolean(item));
    const caution =
      ["drug_interactions", "deficiency", "recommendations"].includes(intent)
        ? "\n\n涉及个体用药、诊断或治疗时，请咨询医生或药师；本回答仅整理知识库证据。"
        : "";
    return {
      session_id: sessionId,
      query,
      normalized_query: normalize(query),
      intent,
      answer_text: `${heading(intent, entities)}\n\n${claims.map((claim) => `- ${claim.text}`).join("\n")}${caution}`,
      claims,
      citations,
      graph_paths: directPaths,
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
      "当前知识库没有足够证据回答这个问题。系统不会使用生成模型补写医学结论。你可以查看下面的相关实体，或换一种更具体的问法。",
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
