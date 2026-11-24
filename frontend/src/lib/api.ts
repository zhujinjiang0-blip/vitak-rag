import type {
  Answer,
  AuditLogItem,
  AuthUser,
  GraphMeta,
  GraphNode,
  Health,
  QAMode,
  ResearchEvidenceResponse,
  ResearchFacets,
  ResearchInsights,
  ResearchOverview,
  SearchResult,
  SnapshotAudit,
  SnapshotDiff,
  SnapshotInfo,
  Subgraph,
  TriageSession,
  UnmetNeedRecord
} from "./types";
import {
  askStaticQuestion,
  getStaticGraphMeta,
  getStaticFullGraph,
  getStaticHealth,
  getStaticSubgraph,
  searchStaticEvidence,
  searchStaticGraph,
  STATIC_DEMO_MODE
} from "./staticDemo";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers
    }
  });
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

export function getGraphMeta(scope = "domain"): Promise<GraphMeta> {
  if (STATIC_DEMO_MODE) return getStaticGraphMeta();
  return jsonRequest<GraphMeta>(`/api/v1/graph/meta?scope=${scope}`);
}

export function searchGraph(
  query: string,
  scope = "domain"
): Promise<{ items: GraphNode[]; total: number }> {
  if (STATIC_DEMO_MODE) return searchStaticGraph(query);
  return jsonRequest(
    `/api/v1/graph/search?q=${encodeURIComponent(query)}&limit=30&scope=${scope}`
  );
}

export function getSubgraph(
  entityIds: string[],
  depth: number,
  domains: string[],
  scope = "domain"
): Promise<Subgraph> {
  if (STATIC_DEMO_MODE) return getStaticSubgraph(entityIds, depth, domains);
  return jsonRequest<Subgraph>("/api/v1/graph/subgraph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      entity_ids: entityIds,
      depth,
      domains,
      limit: 100,
      scope
    })
  });
}

export function getFullGraph(domains: string[], scope = "domain"): Promise<Subgraph> {
  if (STATIC_DEMO_MODE) return getStaticFullGraph(domains);
  return jsonRequest<Subgraph>("/api/v1/graph/full", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domains, scope })
  });
}

export function searchEvidence(query: string, origin = "all"): Promise<{
  items: SearchResult[];
  total: number;
}> {
  if (STATIC_DEMO_MODE) return searchStaticEvidence(query);
  const originParam = origin === "all" ? "" : `&origin=${encodeURIComponent(origin)}`;
  return jsonRequest(
    `/api/v1/search?q=${encodeURIComponent(query)}&limit=20${originParam}`
  );
}

interface ImportResult {
  version?: string;
  snapshot_version?: string;
  rows?: number;
  graph_edges?: number;
  edges_added?: number;
  chunks?: number;
  candidates?: number;
  nodes?: number;
  sources?: number;
  warnings: string[];
}

async function uploadRequest(
  endpoint: string,
  file: File,
  fields: Record<string, string>
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    form.append(key, value);
  }
  const response = await fetch(endpoint, {
    method: "POST",
    credentials: "include",
    body: form
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ImportResult>;
}

export function uploadExternalTriples(
  file: File,
  activate: boolean
): Promise<ImportResult> {
  return uploadRequest(
    "/internal/v1/upload-external-triples",
    file,
    {
      activate: String(activate)
    }
  );
}

export function uploadInternalCsv(
  file: File,
  activate: boolean
): Promise<ImportResult> {
  return uploadRequest(
    "/internal/v1/upload-internal-csv",
    file,
    {
      activate: String(activate)
    }
  );
}

export async function askQuestion(
  query: string,
  sessionId: string | null,
  mode: QAMode,
  handlers: {
    status?: (message: string) => void;
    onAnswer: (answer: Answer) => Promise<void> | void;
  }
): Promise<void> {
  async function emitThinkingSteps() {
    const steps = [
      "正在理解问题并识别询问意图",
      "正在匹配维生素K实体与别名",
      "正在检索真实证据、图谱关系和文献来源",
      "正在汇总证据并整理推理分析",
      "正在核对审核状态、证据充分性与安全边界"
    ];
    for (const step of steps) {
      handlers.status?.(step);
      await new Promise((resolve) => window.setTimeout(resolve, 110));
    }
  }

  if (STATIC_DEMO_MODE) {
    await emitThinkingSteps();
    handlers.status?.("正在组织可追溯回答");
    await handlers.onAnswer(await askStaticQuestion(query, sessionId ?? undefined));
    return;
  }
  await emitThinkingSteps();
  const response = await fetch("/api/v1/qa/stream", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId, mode })
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
      if (event === "generation") {
        handlers.status?.(
          payload.used
            ? "大模型改写已通过证据校验"
            : "已完成确定性证据回退"
        );
      }
      if (event === "done") await handlers.onAnswer(payload as Answer);
    }
  }
}

export function getCurrentUser(): Promise<AuthUser | null> {
  return jsonRequest<AuthUser | null>("/api/v1/auth/session");
}

export async function login(
  username: string,
  password: string
): Promise<AuthUser> {
  const result = await jsonRequest<{ user: AuthUser }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  return result.user;
}

export function logout(): Promise<void> {
  return jsonRequest("/api/v1/auth/logout", { method: "POST" });
}

export function getResearchOverview(): Promise<ResearchOverview> {
  return jsonRequest<ResearchOverview>("/api/v1/research/overview");
}

export function getResearchFacets(): Promise<ResearchFacets> {
  return jsonRequest<ResearchFacets>("/api/v1/research/facets");
}

export function getResearchInsights(): Promise<ResearchInsights> {
  return jsonRequest<ResearchInsights>("/api/v1/research/insights");
}

export function searchResearchEvidence(
  params: Record<string, string | number>
): Promise<ResearchEvidenceResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (String(value).length > 0) search.set(key, String(value));
  }
  return jsonRequest<ResearchEvidenceResponse>(
    `/api/v1/research/evidence?${search.toString()}`
  );
}

export function getSnapshots(): Promise<{ items: SnapshotInfo[] }> {
  return jsonRequest<{ items: SnapshotInfo[] }>("/internal/v1/snapshots");
}

export function getSnapshotAudit(version: string): Promise<SnapshotAudit> {
  return jsonRequest<SnapshotAudit>(
    `/internal/v1/governance/snapshots/${encodeURIComponent(version)}`
  );
}

export function getActiveSnapshotAudit(): Promise<SnapshotAudit> {
  return jsonRequest<SnapshotAudit>("/internal/v1/governance/active");
}

export function getSnapshotDiff(
  fromVersion: string,
  toVersion: string
): Promise<SnapshotDiff> {
  const params = new URLSearchParams({
    from_version: fromVersion,
    to_version: toVersion
  });
  return jsonRequest<SnapshotDiff>(`/internal/v1/governance/diff?${params}`);
}

export function activateSnapshot(
  version: string
): Promise<{ version: string; status: string }> {
  return jsonRequest<{ version: string; status: string }>(
    `/internal/v1/snapshots/${encodeURIComponent(version)}/activate`,
    { method: "POST" }
  );
}

export function getUnmetNeeds(): Promise<{
  items: UnmetNeedRecord[];
  total: number;
}> {
  return jsonRequest<{ items: UnmetNeedRecord[]; total: number }>(
    "/internal/v1/unmet-needs"
  );
}

export function getAuditLogs(): Promise<{
  items: AuditLogItem[];
}> {
  return jsonRequest<{ items: AuditLogItem[] }>("/internal/v1/audit-logs");
}

export function getReviewItems(): Promise<{
  items: Array<{
    id: string;
    job_id: string;
    candidate_type: string;
    status: string;
    reviewer: string | null;
    created_at: string;
    payload: Record<string, unknown>;
  }>;
}> {
  return jsonRequest("/internal/v1/review?status=pending");
}

export function startTriage(): Promise<TriageSession> {
  return jsonRequest<TriageSession>("/api/v1/triage/sessions", {
    method: "POST"
  });
}

export function getTriageSession(sessionId: string): Promise<TriageSession> {
  return jsonRequest<TriageSession>(
    `/api/v1/triage/sessions/${encodeURIComponent(sessionId)}`
  );
}

export function answerTriage(
  sessionId: string,
  questionId: string,
  values: string[],
  action: "next" | "back" = "next"
): Promise<TriageSession> {
  return jsonRequest<TriageSession>(
    `/api/v1/triage/sessions/${encodeURIComponent(sessionId)}/answer`,
    {
      method: "POST",
      body: JSON.stringify({
        question_id: questionId,
        values,
        action
      })
    }
  );
}
