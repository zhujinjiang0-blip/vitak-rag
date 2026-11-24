export type EvidenceSufficiency = "sufficient" | "partial" | "none";
export type ClaimType =
  | "general"
  | "association"
  | "intervention"
  | "mechanism"
  | "negative"
  | "exploratory"
  | "interaction"
  | "conflict";
export type DataOrigin = "internal" | "external" | "public" | "synthetic";
export type AccessScope = "private" | "controlled" | "public";
export type QAMode = "domain" | "research" | "comparison";
export type UserRole = "researcher" | "admin";

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
  source_classification: string;
  data_origin: DataOrigin;
  data_owner: string;
  access_scope: AccessScope;
  publisher: string;
  published_at: string;
  url: string;
  evidence_level: string;
  locator: string;
  snippet: string;
  is_demo: boolean;
  review_status?: string;
  input_status?: string;
  fusion_status?: string;
  evidence_status?: string;
  answer_eligible?: boolean;
  source_version?: string;
  source_locator?: string;
  analysis_context?: string;
  effect_size?: string;
  p_value?: string;
  q_value?: string;
  sample_n?: string;
  model_type?: string;
  test_family?: string;
  core_48?: boolean;
  retention_status?: string;
  conflict_id?: string;
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
  claim_type?: ClaimType;
  boundary_note?: string | null;
}

export interface EvidenceComparison {
  id: string;
  status:
    | "significance_difference"
    | "direction_difference"
    | "evidence_layer_difference"
    | "context_difference"
    | "reported_difference"
    | string;
  summary: string;
  claim_ids: string[];
  evidence_ids: string[];
}

export interface GenerationInfo {
  status: "disabled" | "not_attempted" | "generated" | "fallback";
  configured: boolean;
  used: boolean;
  provider: string;
  model: string;
  semantic_parse_used: boolean;
  accepted_claim_count: number;
  rejected_claim_count: number;
  fallback_reason: string;
  verification: string;
  latency_ms: number;
}

export interface Answer {
  session_id: string;
  query: string;
  normalized_query: string;
  intent: string;
  answer_text: string;
  claims: Claim[];
  citations: Citation[];
  comparisons?: EvidenceComparison[];
  graph_paths: GraphPath[];
  sufficiency: EvidenceSufficiency;
  safety_notice: string | null;
  related_entities: GraphNode[];
  data_version: DataVersion;
  elapsed_ms: number;
  mode?: QAMode;
  data_scope?: string[];
  applied_filters?: Record<string, unknown>;
  generation?: GenerationInfo;
}

export interface Health {
  status: string;
  runtime_llm: boolean;
  llm_provider?: string;
  llm_model?: string;
  llm_configured?: boolean;
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
  source_classification: string;
  data_origin: DataOrigin;
  data_owner: string;
  access_scope: AccessScope;
  evidence_level?: string;
  source_type: string;
  review_status: string;
  input_status: string;
  fusion_status: string;
  evidence_status: string;
  graph_display_role: string;
  answer_eligible: boolean;
  source_record_id: string;
  source_version: string;
  source_locator: string;
  url: string;
  predicate: string;
  snippet: string;
  entity_ids: string[];
  evidence_json: Record<string, unknown>;
  score: number;
  is_demo: boolean;
  test_family?: string;
  analysis_context?: string;
  effect_size?: string;
  ci_low?: string;
  ci_high?: string;
  p_value?: string;
  q_value?: string;
  sample_n?: string;
  model_type?: string;
  core_48?: boolean;
  retention_status?: string;
  conflict_id?: string;
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

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  active: boolean;
  expires_at: string | null;
  session_expires_at: string | null;
}

export interface ResearchOverview {
  data_version: string;
  total_internal_records: number;
  core_records: number;
  contextual_records: number;
  core_contextual_overlap: number;
  source_count: number;
  grade_distribution: Record<string, number>;
  result_distribution: Record<string, number>;
  test_family_distribution: Record<string, number>;
  cohort_description: string;
  data_scope: string;
  scientific_review_status: string;
}

export interface ResearchDistributionItem {
  key: string;
  label: string;
  count: number;
  percentage: number;
}

export interface ResearchEffectPoint {
  evidence_id: string;
  label: string;
  value: number;
  ci_low: number | null;
  ci_high: number | null;
  result_status: string;
  evidence_level: string;
}

export interface ResearchEffectSeries {
  id: string;
  title: string;
  outcome: string;
  model_type: string;
  analysis_context: string;
  unit: string;
  reference_value: number;
  points: ResearchEffectPoint[];
}

export interface ResearchInsights {
  data_version: string;
  total_records: number;
  match_status_available: boolean;
  match_note: string;
  match_categories: ResearchDistributionItem[];
  governance_categories: ResearchDistributionItem[];
  status_distribution: ResearchDistributionItem[];
  grade_distribution: ResearchDistributionItem[];
  effect_series: ResearchEffectSeries[];
  limitations: string[];
}

export interface ResearchFacetOption {
  value: string;
  label: string;
  count: number;
}

export interface ResearchFacets {
  test_families: ResearchFacetOption[];
  evidence_levels: ResearchFacetOption[];
  result_statuses: ResearchFacetOption[];
  review_statuses: ResearchFacetOption[];
  outcomes: ResearchFacetOption[];
}

export interface ResearchEvidenceResponse {
  items: SearchResult[];
  total: number;
  page: number;
  page_size: number;
  facets: ResearchFacets;
  applied_filters: Record<string, unknown>;
}

export interface UnmetNeedRecord {
  id: string;
  session_id: string;
  query: string;
  mode: string;
  intent: string;
  reason: string;
  detail: string;
  data_scope: string[];
  data_version: string;
  status: string;
  reviewer_note: string;
  created_at: string;
  updated_at: string;
}

export interface SnapshotInfo {
  version: string;
  created_at: string;
  is_demo: boolean;
  entity_count: number;
  relation_count: number;
  source_count: number;
  chunk_count: number;
  path: string;
}

export interface GovernanceCheck {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail" | "unavailable" | string;
  value: number | string;
  detail: string;
}

export interface SnapshotAudit {
  version: string;
  created_at: string | null;
  is_demo: boolean;
  active: boolean;
  counts: Record<string, number>;
  source_types: Record<string, number>;
  origins: Record<string, number>;
  access_scopes: Record<string, number>;
  review_statuses: Record<string, number>;
  evidence_statuses: Record<string, number>;
  checks: GovernanceCheck[];
  warnings: string[];
  input_files: Array<{ name: string; sha256: string; rows: number }>;
}

export interface SnapshotDiff {
  from_version: string;
  to_version: string;
  count_deltas: Record<string, number>;
  distribution_deltas: Record<string, Record<string, number>>;
  added_input_files: string[];
  removed_input_files: string[];
}

export interface AuditLogItem {
  id: string;
  actor_id: string | null;
  action: string;
  target: string;
  metadata_json: string;
  created_at: string;
}

export interface TriageOption {
  value: string;
  label: string;
  description: string;
}

export interface TriageQuestion {
  id: string;
  prompt: string;
  help_text: string;
  multiple: boolean;
  options: TriageOption[];
}

export interface TriageOutcome {
  level: "emergency" | "professional_review" | "insufficient_information";
  title: string;
  summary: string;
  recommendations: string[];
  citations: Citation[];
  cannot_conclude: string;
}

export interface TriageProgress {
  current: number;
  total: number;
}

export interface TriageSession {
  session_id: string;
  status: "in_progress" | "completed" | "expired";
  progress: TriageProgress;
  question: TriageQuestion | null;
  answers: Record<string, string[]>;
  outcome: TriageOutcome | null;
}
