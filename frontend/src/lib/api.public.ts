import type {
  Answer,
  GraphMeta,
  GraphNode,
  Health,
  QAMode,
  SearchResult,
  Subgraph,
  TriageSession
} from "./types";
import {
  askStaticQuestion,
  getStaticFullGraph,
  getStaticGraphMeta,
  getStaticHealth,
  getStaticSubgraph,
  searchStaticEvidence,
  searchStaticGraph
} from "./staticDemo";
import {
  answerStaticTriage,
  getStaticTriageSession,
  startStaticTriage
} from "./triageStatic";

export function getHealth(): Promise<Health> {
  return getStaticHealth();
}

export function getGraphMeta(): Promise<GraphMeta> {
  return getStaticGraphMeta();
}

export function searchGraph(
  query: string
): Promise<{ items: GraphNode[]; total: number }> {
  return searchStaticGraph(query);
}

export function getSubgraph(
  entityIds: string[],
  depth: number,
  domains: string[]
): Promise<Subgraph> {
  return getStaticSubgraph(entityIds, depth, domains);
}

export function getFullGraph(domains: string[]): Promise<Subgraph> {
  return getStaticFullGraph(domains);
}

export function searchEvidence(query: string, _origin = "all"): Promise<{
  items: SearchResult[];
  total: number;
}> {
  return searchStaticEvidence(query);
}

export async function askQuestion(
  query: string,
  sessionId: string | null,
  _mode: QAMode,
  handlers: {
    status?: (message: string) => void;
    onAnswer: (answer: Answer) => Promise<void> | void;
  }
): Promise<void> {
  const steps = [
    "正在理解问题并识别询问意图",
    "正在匹配维生素K实体与别名",
    "正在检索公开文献和结构化证据",
    "正在核对来源范围与证据充分性"
  ];
  for (const step of steps) {
    handlers.status?.(step);
    await new Promise((resolve) => window.setTimeout(resolve, 110));
  }
  handlers.status?.("正在组织可追溯回答");
  await handlers.onAnswer(await askStaticQuestion(query, sessionId ?? undefined));
}

export function startTriage(): Promise<TriageSession> {
  return startStaticTriage();
}

export function getTriageSession(sessionId: string): Promise<TriageSession> {
  return getStaticTriageSession(sessionId);
}

export function answerTriage(
  sessionId: string,
  questionId: string,
  values: string[],
  action: "next" | "back" = "next"
): Promise<TriageSession> {
  return answerStaticTriage(sessionId, questionId, values, action);
}
