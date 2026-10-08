import type {
  Answer,
  GraphMeta,
  GraphNode,
  Health,
  SearchResult,
  Subgraph
} from "./types";
import {
  askStaticQuestion,
  getStaticGraphMeta,
  getStaticHealth,
  getStaticSubgraph,
  searchStaticEvidence,
  searchStaticGraph,
  STATIC_DEMO_MODE
} from "./staticDemo";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${response.status} ${message}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<Health> {
  if (STATIC_DEMO_MODE) return getStaticHealth();
  return jsonRequest<Health>("/api/v1/health");
}

export function getGraphMeta(): Promise<GraphMeta> {
  if (STATIC_DEMO_MODE) return getStaticGraphMeta();
  return jsonRequest<GraphMeta>("/api/v1/graph/meta");
}

export function searchGraph(query: string): Promise<{ items: GraphNode[]; total: number }> {
  if (STATIC_DEMO_MODE) return searchStaticGraph(query);
  return jsonRequest(`/api/v1/graph/search?q=${encodeURIComponent(query)}&limit=30`);
}

export function getSubgraph(
  entityIds: string[],
  depth: number,
  domains: string[]
): Promise<Subgraph> {
  if (STATIC_DEMO_MODE) return getStaticSubgraph(entityIds, depth, domains);
  return jsonRequest<Subgraph>("/api/v1/graph/subgraph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      entity_ids: entityIds,
      depth,
      domains,
      limit: 100
    })
  });
}

export function searchEvidence(query: string): Promise<{
  items: SearchResult[];
  total: number;
}> {
  if (STATIC_DEMO_MODE) return searchStaticEvidence(query);
  return jsonRequest(`/api/v1/search?q=${encodeURIComponent(query)}&limit=20`);
}

interface ImportResult {
  snapshot_version: string;
  rows?: number;
  chunks?: number;
  edges_added?: number;
  candidates?: number;
  warnings: string[];
}

async function uploadRequest(
  endpoint: string,
  file: File,
  fields: Record<string, string>,
  token: string
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    form.append(key, value);
  }
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "X-Internal-Token": token },
    body: form
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ImportResult>;
}

export function uploadExternalTriples(
  file: File,
  dataOwner: string,
  activate: boolean,
  token: string
): Promise<ImportResult> {
  return uploadRequest(
    "/internal/v1/upload-external-triples",
    file,
    {
      data_owner: dataOwner,
      activate: String(activate)
    },
    token
  );
}

export function uploadInternalCsv(
  file: File,
  dataOwner: string,
  sourceType: string,
  sourceClassification: string,
  activate: boolean,
  token: string
): Promise<ImportResult> {
  return uploadRequest(
    "/internal/v1/upload-internal-csv",
    file,
    {
      data_owner: dataOwner,
      source_type: sourceType,
      source_classification: sourceClassification,
      activate: String(activate)
    },
    token
  );
}

export async function askQuestion(
  query: string,
  sessionId: string | null,
  handlers: {
    status?: (message: string) => void;
    onAnswer: (answer: Answer) => void;
  }
): Promise<void> {
  if (STATIC_DEMO_MODE) {
    handlers.status?.("正在加载浏览器端知识库");
    handlers.onAnswer(await askStaticQuestion(query));
    return;
  }
  const response = await fetch("/api/v1/qa/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId })
  });
  if (!response.ok || !response.body) {
    throw new Error(`问答接口失败：${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventLine = block
        .split("\n")
        .find((line) => line.startsWith("event: "));
      const dataLine = block
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) continue;
      const event = eventLine.slice(7);
      const payload = JSON.parse(dataLine.slice(6));
      if (event === "status") handlers.status?.(payload.message);
      if (event === "done") handlers.onAnswer(payload as Answer);
    }
  }
}
