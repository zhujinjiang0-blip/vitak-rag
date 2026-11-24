import type {
  Answer,
  GraphEdge,
  GraphNode,
  GraphPath,
  Subgraph
} from "./types";

export const GRAPH_PATH_HANDOFF_KEY = "vitak-rag:graph-path-handoff:v1";
const MAX_HANDOFF_AGE_MS = 24 * 60 * 60 * 1000;

export interface GraphPathHandoff {
  id: string;
  kind: "paths" | "entities";
  query: string;
  intent: string;
  createdAt: number;
  dataVersion: string;
  paths: GraphPath[];
  relatedEntities: GraphNode[];
}

export function createGraphPathHandoff(answer: Answer): GraphPathHandoff | null {
  const kind =
    answer.graph_paths.length > 0
      ? "paths"
      : answer.related_entities.length > 0
        ? "entities"
        : null;
  if (!kind) return null;
  return {
    id: `graph-handoff-${crypto.randomUUID()}`,
    kind,
    query: answer.query,
    intent: answer.intent,
    createdAt: Date.now(),
    dataVersion: answer.data_version.version,
    paths: answer.graph_paths,
    relatedEntities: answer.related_entities
  };
}

export function saveGraphPathHandoff(handoff: GraphPathHandoff) {
  try {
    sessionStorage.setItem(GRAPH_PATH_HANDOFF_KEY, JSON.stringify(handoff));
  } catch {
    // Session storage is optional; the graph page still supports normal navigation.
  }
}

export function readGraphPathHandoff(): GraphPathHandoff | null {
  try {
    const raw = sessionStorage.getItem(GRAPH_PATH_HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GraphPathHandoff>;
    const valid =
      typeof parsed.id === "string" &&
      (parsed.kind === "paths" || parsed.kind === "entities") &&
      typeof parsed.query === "string" &&
      typeof parsed.intent === "string" &&
      typeof parsed.createdAt === "number" &&
      typeof parsed.dataVersion === "string" &&
      Array.isArray(parsed.paths) &&
      Array.isArray(parsed.relatedEntities);
    if (
      !valid ||
      Date.now() - Number(parsed.createdAt) > MAX_HANDOFF_AGE_MS
    ) {
      clearGraphPathHandoff();
      return null;
    }
    return parsed as GraphPathHandoff;
  } catch {
    clearGraphPathHandoff();
    return null;
  }
}

export function clearGraphPathHandoff() {
  try {
    sessionStorage.removeItem(GRAPH_PATH_HANDOFF_KEY);
  } catch {
    // Ignore unavailable session storage.
  }
}

export function buildGraphPathSubgraph(handoff: GraphPathHandoff): Subgraph {
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();

  handoff.paths.forEach((path) => {
    path.nodes.forEach((node) => nodes.set(node.id, node));
    path.edges.forEach((edge) => edges.set(edge.id, edge));
  });
  handoff.relatedEntities.forEach((node) => nodes.set(node.id, node));

  const validEdges = [...edges.values()].filter(
    (edge) => nodes.has(edge.source) && nodes.has(edge.target)
  );
  return {
    nodes: [...nodes.values()],
    edges: validEdges,
    data_version: {
      version: handoff.dataVersion,
      created_at: new Date(handoff.createdAt).toISOString(),
      is_demo: false,
      entity_count: nodes.size,
      relation_count: validEdges.length,
      source_count: 0,
      chunk_count: 0
    }
  };
}
