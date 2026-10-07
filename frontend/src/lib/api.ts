import type {
  Answer,
  GraphMeta,
  GraphNode,
  Health,
  SearchResult,
  Subgraph
} from "./types";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${response.status} ${message}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<Health> {
  return jsonRequest<Health>("/api/v1/health");
}

export function getGraphMeta(): Promise<GraphMeta> {
  return jsonRequest<GraphMeta>("/api/v1/graph/meta");
}

export function searchGraph(query: string): Promise<{ items: GraphNode[]; total: number }> {
  return jsonRequest(`/api/v1/graph/search?q=${encodeURIComponent(query)}&limit=30`);
}

export function getSubgraph(
  entityIds: string[],
  depth: number,
  domains: string[]
): Promise<Subgraph> {
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
  return jsonRequest(`/api/v1/search?q=${encodeURIComponent(query)}&limit=20`);
}

export async function askQuestion(
  query: string,
  sessionId: string | null,
  handlers: {
    status?: (message: string) => void;
    onAnswer: (answer: Answer) => void;
  }
): Promise<void> {
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

