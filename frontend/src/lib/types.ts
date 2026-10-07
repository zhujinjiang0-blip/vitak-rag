export type EvidenceSufficiency = "sufficient" | "partial" | "none";

export interface DataVersion {
  version: string;
  created_at: string;
  is_demo: boolean;
  entity_count: number;
  relation_count: number;
  source_count: number;
  chunk_count: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  domain: string;
  summary: string;
  aliases: string[];
  is_demo: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  predicate: string;
  evidence_ids: string[];
  evidence_level: string;
  confidence: number;
  is_demo: boolean;
}

export interface Citation {
  id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  publisher: string;
  published_at: string;
  url: string;
  evidence_level: string;
  locator: string;
  snippet: string;
  is_demo: boolean;
}

export interface GraphPath {
  nodes: GraphNode[];
  edges: GraphEdge[];
  evidence_ids: string[];
}

export interface Claim {
  id: string;
  text: string;
  evidence_ids: string[];
  relation: string | null;
}

export interface Answer {
  session_id: string;
  query: string;
  normalized_query: string;
  intent: string;
  answer_text: string;
  claims: Claim[];
  citations: Citation[];
  graph_paths: GraphPath[];
  sufficiency: EvidenceSufficiency;
  safety_notice: string | null;
  related_entities: GraphNode[];
  data_version: DataVersion;
  elapsed_ms: number;
}

export interface Health {
  status: string;
  runtime_llm: boolean;
  data_version: DataVersion;
  graph_backend: string;
  vector_backend: string;
  metadata_backend: string;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  source_id: string;
  title: string;
  snippet: string;
  entity_ids: string[];
  score: number;
  is_demo: boolean;
}

export interface Subgraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  data_version: DataVersion;
}

export interface GraphMeta {
  domains: string[];
  types: string[];
  stats: { nodes: number; edges: number };
  data_version: DataVersion;
}

