from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    NONE = "none"


class ClaimType(StrEnum):
    GENERAL = "general"
    ASSOCIATION = "association"
    INTERVENTION = "intervention"
    MECHANISM = "mechanism"
    NEGATIVE = "negative"
    EXPLORATORY = "exploratory"
    INTERACTION = "interaction"
    CONFLICT = "conflict"


class DataOrigin(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    PUBLIC = "public"
    SYNTHETIC = "synthetic"


class AccessScope(StrEnum):
    PRIVATE = "private"
    CONTROLLED = "controlled"
    PUBLIC = "public"


class QAMode(StrEnum):
    DOMAIN = "domain"
    RESEARCH = "research"
    COMPARISON = "comparison"


class ResearchCollection(StrEnum):
    ALL = "all"
    CORE = "core"
    CONTEXTUAL = "contextual"


class UserRole(StrEnum):
    RESEARCHER = "researcher"
    ADMIN = "admin"


class GenerationStatus(StrEnum):
    DISABLED = "disabled"
    NOT_ATTEMPTED = "not_attempted"
    GENERATED = "generated"
    FALLBACK = "fallback"


class DataVersion(BaseModel):
    version: str
    created_at: datetime
    is_demo: bool = True
    entity_count: int = 0
    relation_count: int = 0
    source_count: int = 0
    chunk_count: int = 0


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    domain: str
    summary: str = ""
    aliases: list[str] = Field(default_factory=list)
    is_demo: bool = True


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    predicate: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_level: str = "demo"
    confidence: float = 0.5
    is_demo: bool = True


class Citation(BaseModel):
    id: str
    source_id: str
    source_title: str
    source_type: str
    source_classification: str = ""
    data_origin: DataOrigin = DataOrigin.PUBLIC
    data_owner: str = ""
    access_scope: AccessScope = AccessScope.PUBLIC
    publisher: str = ""
    published_at: str = ""
    url: str = ""
    evidence_level: str = "demo"
    locator: str = ""
    snippet: str
    is_demo: bool = True
    review_status: str = ""
    input_status: str = ""
    fusion_status: str = ""
    evidence_status: str = ""
    source_version: str = ""
    source_locator: str = ""
    analysis_context: str = ""
    effect_size: str = ""
    p_value: str = ""
    q_value: str = ""
    sample_n: str = ""
    model_type: str = ""
    test_family: str = ""
    core_48: bool = False
    retention_status: str = ""
    conflict_id: str = ""


class GraphPath(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    evidence_ids: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    id: str
    text: str
    evidence_ids: list[str] = Field(min_length=1)
    relation: str | None = None
    claim_type: ClaimType = ClaimType.GENERAL
    boundary_note: str | None = None


class EvidenceComparison(BaseModel):
    id: str
    status: str
    summary: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class GenerationInfo(BaseModel):
    status: GenerationStatus = GenerationStatus.DISABLED
    configured: bool = False
    used: bool = False
    provider: str = ""
    model: str = ""
    semantic_parse_used: bool = False
    accepted_claim_count: int = 0
    rejected_claim_count: int = 0
    fallback_reason: str = ""
    verification: str = "not_attempted"
    latency_ms: int = 0
    endpoint_class: str = ""
    evidence_policy: str = "public_only"
    protected_evidence_allowed: bool = False


class Answer(BaseModel):
    session_id: str
    query: str
    normalized_query: str
    intent: str
    answer_text: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    comparisons: list[EvidenceComparison] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    sufficiency: EvidenceSufficiency
    safety_notice: str | None = None
    related_entities: list[GraphNode] = Field(default_factory=list)
    data_version: DataVersion
    elapsed_ms: int = 0
    mode: QAMode = QAMode.DOMAIN
    data_scope: list[str] = Field(default_factory=lambda: ["external"])
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    generation: GenerationInfo = Field(default_factory=GenerationInfo)


class QARequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None
    mode: QAMode = QAMode.DOMAIN
    filters: dict[str, Any] = Field(default_factory=dict)


class GraphSearchResponse(BaseModel):
    items: list[GraphNode]
    total: int


class SubgraphRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=10)
    depth: int = Field(default=1, ge=1, le=2)
    domains: list[str] = Field(default_factory=list)
    limit: int = Field(default=80, ge=10, le=300)
    scope: str = Field(default="domain", pattern="^(domain|research|comparison)$")


class FullGraphRequest(BaseModel):
    domains: list[str] = Field(default_factory=list)
    scope: str = Field(default="domain", pattern="^(domain|research|comparison)$")


class SubgraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    data_version: DataVersion


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    source_id: str
    title: str
    source_classification: str = ""
    data_origin: DataOrigin = DataOrigin.PUBLIC
    data_owner: str = ""
    access_scope: AccessScope = AccessScope.PUBLIC
    evidence_level: str = ""
    source_type: str = ""
    review_status: str = "accepted"
    input_status: str = "adopted"
    fusion_status: str = "accepted"
    evidence_status: str = ""
    graph_display_role: str = ""
    answer_eligible: bool = True
    source_record_id: str = ""
    source_version: str = ""
    source_locator: str = ""
    url: str = ""
    predicate: str = ""
    snippet: str
    entity_ids: list[str] = Field(default_factory=list)
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    score: float
    is_demo: bool = True
    test_family: str = ""
    analysis_context: str = ""
    effect_size: str = ""
    ci_low: str = ""
    ci_high: str = ""
    p_value: str = ""
    q_value: str = ""
    sample_n: str = ""
    model_type: str = ""
    core_48: bool = False
    retention_status: str = ""
    conflict_id: str = ""


class SearchResponse(BaseModel):
    items: list[SearchResult]
    total: int


class IngestRequest(BaseModel):
    path: str
    source_title: str | None = None
    source_type: str = "document"
    data_origin: DataOrigin = DataOrigin.INTERNAL
    data_owner: str = "毕业设计内部资料"
    access_scope: AccessScope = AccessScope.PRIVATE
    source_classification: str = ""
    use_llm: bool = False
    activate: bool = False


class IngestResponse(BaseModel):
    job_id: str
    snapshot_version: str
    documents: int
    chunks: int
    candidates: int
    warnings: list[str] = Field(default_factory=list)


class ExternalTripleImportRequest(BaseModel):
    path: str
    data_owner: str = "已发表维生素 K 研究文献"
    activate: bool = False


class ExternalTripleImportResponse(BaseModel):
    snapshot_version: str
    rows: int
    skipped_rows: int
    sources: int
    nodes_added: int
    edges_added: int
    warnings: list[str] = Field(default_factory=list)


class EvidenceTableImportRequest(BaseModel):
    paths: list[str] = Field(min_length=1)
    version: str = "vitak-real-2026.11"
    activate: bool = False
    build_vectors: bool = True


class ReviewDecisionRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    decision: str = Field(pattern="^(approve|reject)$")
    reviewer: str = "local"


class HealthResponse(BaseModel):
    status: str
    runtime_llm: bool
    llm_provider: str = ""
    llm_model: str = ""
    llm_configured: bool = False
    llm_endpoint_class: str = ""
    llm_protected_evidence_allowed: bool = False
    data_version: DataVersion
    graph_backend: str
    vector_backend: str
    metadata_backend: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class AuthUser(BaseModel):
    id: str
    username: str
    display_name: str
    role: UserRole
    active: bool
    expires_at: str | None = None
    session_expires_at: str | None = None


class LoginResponse(BaseModel):
    user: AuthUser


class ResearchFacetOption(BaseModel):
    value: str
    label: str
    count: int


class ResearchFacets(BaseModel):
    test_families: list[ResearchFacetOption]
    evidence_levels: list[ResearchFacetOption]
    result_statuses: list[ResearchFacetOption]
    review_statuses: list[ResearchFacetOption]
    outcomes: list[ResearchFacetOption]


class ResearchOverview(BaseModel):
    data_version: str
    total_internal_records: int
    core_records: int
    contextual_records: int
    core_contextual_overlap: int
    source_count: int
    grade_distribution: dict[str, int]
    result_distribution: dict[str, int]
    test_family_distribution: dict[str, int]
    cohort_description: str
    data_scope: str = "internal/private"
    scientific_review_status: str = "pending_scientific_owner"


class ResearchDistributionItem(BaseModel):
    key: str
    label: str
    count: int
    percentage: float


class ResearchEffectPoint(BaseModel):
    evidence_id: str
    label: str
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    result_status: str
    evidence_level: str


class ResearchEffectSeries(BaseModel):
    id: str
    title: str
    outcome: str
    model_type: str
    analysis_context: str
    unit: str = "未报告单位"
    reference_value: float = 0
    points: list[ResearchEffectPoint] = Field(default_factory=list)


class ResearchInsights(BaseModel):
    data_version: str
    total_records: int
    match_status_available: bool
    match_note: str
    match_categories: list[ResearchDistributionItem] = Field(default_factory=list)
    governance_categories: list[ResearchDistributionItem] = Field(default_factory=list)
    status_distribution: list[ResearchDistributionItem] = Field(default_factory=list)
    grade_distribution: list[ResearchDistributionItem] = Field(default_factory=list)
    effect_series: list[ResearchEffectSeries] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ResearchEvidenceResponse(BaseModel):
    items: list[SearchResult]
    total: int
    page: int
    page_size: int
    facets: ResearchFacets
    applied_filters: dict[str, Any] = Field(default_factory=dict)


class UnmetNeedRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None
    mode: QAMode = QAMode.DOMAIN
    reason: str = Field(default="evidence_insufficient", max_length=120)
    detail: str = Field(default="", max_length=1000)
    data_scope: list[str] = Field(default_factory=lambda: ["external"])


class UnmetNeedRecord(BaseModel):
    id: str
    session_id: str = ""
    query: str
    mode: str
    intent: str = ""
    reason: str
    detail: str = ""
    data_scope: list[str] = Field(default_factory=list)
    data_version: str
    status: str = "pending_review"
    reviewer_note: str = ""
    created_at: str
    updated_at: str


class UnmetNeedsResponse(BaseModel):
    items: list[UnmetNeedRecord]
    total: int


class GovernanceCheck(BaseModel):
    key: str
    label: str
    status: str
    value: int | float | str
    detail: str = ""


class SnapshotAudit(BaseModel):
    version: str
    created_at: str | None = None
    is_demo: bool = False
    active: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    source_types: dict[str, int] = Field(default_factory=dict)
    origins: dict[str, int] = Field(default_factory=dict)
    access_scopes: dict[str, int] = Field(default_factory=dict)
    review_statuses: dict[str, int] = Field(default_factory=dict)
    evidence_statuses: dict[str, int] = Field(default_factory=dict)
    checks: list[GovernanceCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    input_files: list[dict[str, Any]] = Field(default_factory=list)


class SnapshotDiff(BaseModel):
    from_version: str
    to_version: str
    count_deltas: dict[str, int] = Field(default_factory=dict)
    distribution_deltas: dict[str, dict[str, int]] = Field(default_factory=dict)
    added_input_files: list[str] = Field(default_factory=list)
    removed_input_files: list[str] = Field(default_factory=list)


class TriageOption(BaseModel):
    value: str
    label: str
    description: str = ""


class TriageQuestion(BaseModel):
    id: str
    prompt: str
    help_text: str = ""
    multiple: bool = False
    options: list[TriageOption] = Field(default_factory=list)


class TriageOutcome(BaseModel):
    level: str = Field(pattern="^(emergency|professional_review|insufficient_information)$")
    title: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    cannot_conclude: str = (
        "该自查不能诊断维生素K缺乏，也不能判断个人是否需要补充或确定剂量。"
    )


class TriageProgress(BaseModel):
    current: int
    total: int


class TriageSessionResponse(BaseModel):
    session_id: str
    status: str = Field(pattern="^(in_progress|completed|expired)$")
    progress: TriageProgress
    question: TriageQuestion | None = None
    answers: dict[str, list[str]] = Field(default_factory=dict)
    outcome: TriageOutcome | None = None


class TriageAnswerRequest(BaseModel):
    question_id: str
    values: list[str] = Field(default_factory=list, max_length=10)
    action: str = Field(default="next", pattern="^(next|back)$")
