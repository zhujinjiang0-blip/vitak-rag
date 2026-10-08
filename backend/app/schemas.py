from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    NONE = "none"


class DataOrigin(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    PUBLIC = "public"
    SYNTHETIC = "synthetic"


class AccessScope(StrEnum):
    PRIVATE = "private"
    CONTROLLED = "controlled"
    PUBLIC = "public"


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


class GraphPath(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    evidence_ids: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    id: str
    text: str
    evidence_ids: list[str] = Field(min_length=1)
    relation: str | None = None


class Answer(BaseModel):
    session_id: str
    query: str
    normalized_query: str
    intent: str
    answer_text: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    sufficiency: EvidenceSufficiency
    safety_notice: str | None = None
    related_entities: list[GraphNode] = Field(default_factory=list)
    data_version: DataVersion
    elapsed_ms: int = 0


class QARequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None


class GraphSearchResponse(BaseModel):
    items: list[GraphNode]
    total: int


class SubgraphRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=10)
    depth: int = Field(default=1, ge=1, le=2)
    domains: list[str] = Field(default_factory=list)
    limit: int = Field(default=80, ge=10, le=300)


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
    snippet: str
    entity_ids: list[str] = Field(default_factory=list)
    score: float
    is_demo: bool = True


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


class ReviewDecisionRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    decision: str = Field(pattern="^(approve|reject)$")
    reviewer: str = "local"


class HealthResponse(BaseModel):
    status: str
    runtime_llm: bool
    data_version: DataVersion
    graph_backend: str
    vector_backend: str
    metadata_backend: str
