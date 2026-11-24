from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas import (
    Answer,
    AuthUser,
    EvidenceSufficiency,
    EvidenceTableImportRequest,
    ExternalTripleImportRequest,
    ExternalTripleImportResponse,
    FullGraphRequest,
    GraphSearchResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    LoginRequest,
    LoginResponse,
    QAMode,
    QARequest,
    ResearchEvidenceResponse,
    ResearchInsights,
    ResearchOverview,
    ReviewDecisionRequest,
    SearchResponse,
    SearchResult,
    SnapshotAudit,
    SnapshotDiff,
    SubgraphRequest,
    SubgraphResponse,
    TriageAnswerRequest,
    TriageSessionResponse,
    UnmetNeedRecord,
    UnmetNeedRequest,
    UnmetNeedsResponse,
    UserRole,
)
from app.services.evidence_tables import EvidenceTableImporter
from app.services.external_triples import ExternalTripleImporter
from app.services.ingest import IngestionService
from app.services.qa_orchestrator import RuntimeQAService
from app.services.research import ResearchService
from app.services.triage import TriageService

router = APIRouter()


def _engine(request: Request):
    return request.app.state.engine


def _snapshot(request: Request):
    return request.app.state.snapshot


def _manager(request: Request):
    return request.app.state.snapshot_manager


def _known_snapshot_version(request: Request, version: str) -> str:
    known = {item["version"] for item in _manager(request).list()}
    if version not in known:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return version


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _search_evidence_json(row: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object(row.get("evidence_metadata_json"))
    payload.update(
        {
            "evidence_id": row.get("evidence_id") or row.get("id"),
            "chunk_id": row.get("id") or row.get("chunk_id"),
            "edge_id": row.get("edge_id") or payload.get("edge_id", ""),
            "document_id": row.get("document_id"),
            "source_id": row.get("source_id"),
            "source_title": row.get("title"),
            "source_type": row.get("evidence_source_type") or row.get("source_type"),
            "source_classification": row.get("source_classification"),
            "data_origin": row.get("data_origin"),
            "data_owner": row.get("data_owner"),
            "access_scope": row.get("access_scope"),
            "publisher": row.get("publisher", ""),
            "published_at": row.get("published_at", ""),
            "url": row.get("url", ""),
            "review_status": row.get("review_status"),
            "input_status": row.get("input_status"),
            "fusion_status": row.get("fusion_status"),
            "evidence_status": row.get("evidence_status"),
            "graph_display_role": row.get("graph_display_role"),
            "answer_eligible": bool(row.get("answer_eligible")),
            "source_record_id": row.get("source_record_id"),
            "source_version": row.get("source_version"),
            "source_locator": row.get("source_locator") or row.get("locator"),
            "snippet": row.get("text") or row.get("chunk_text"),
            "entity_ids": json.loads(row.get("entity_ids_json") or "[]"),
        }
    )
    return payload


def _source_types_for_origin(origin: str | None) -> set[str] | None:
    if origin == "internal":
        return {"internal"}
    if origin == "external":
        return _external_source_types()
    return None


def _auth(request: Request):
    return request.app.state.auth


def _session_token(request: Request) -> str | None:
    cookie_name = request.app.state.settings.session_cookie_name
    return request.cookies.get(cookie_name)


def _optional_user(request: Request) -> AuthUser | None:
    return _auth(request).resolve_session(_session_token(request))


def _require_user(request: Request) -> AuthUser:
    user = _optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="research login required")
    return user


def _require_admin(request: Request) -> AuthUser:
    user = _require_user(request)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="administrator role required")
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="internal API is localhost-only")
    return user


def _research(request: Request) -> ResearchService:
    return ResearchService(request.app.state.settings, _snapshot(request))


def _runtime_qa(request: Request) -> RuntimeQAService:
    return RuntimeQAService(
        request.app.state.settings,
        _snapshot(request),
        llm=request.app.state.runtime_llm,
    )


def _triage(request: Request) -> TriageService:
    return request.app.state.triage


def _external_source_types() -> set[str]:
    return {"literature", "structured", "public", "synthetic", "legacy", ""}


@router.post("/api/v1/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    authenticated = _auth(request).authenticate(payload.username, payload.password)
    if not authenticated:
        raise HTTPException(status_code=401, detail="invalid username or password")
    user, token = authenticated
    response.set_cookie(
        request.app.state.settings.session_cookie_name,
        token,
        max_age=request.app.state.settings.session_ttl_hours * 3600,
        httponly=True,
        secure=request.app.state.settings.env == "production",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=user)


@router.post("/api/v1/auth/logout")
def logout(request: Request, response: Response):
    user = _optional_user(request)
    _auth(request).logout(_session_token(request), user.id if user else None)
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}


@router.get("/api/v1/auth/me", response_model=AuthUser)
def current_user(request: Request):
    return _require_user(request)


@router.get("/api/v1/auth/session", response_model=AuthUser | None)
def current_session(request: Request):
    return _optional_user(request)


@router.get("/api/v1/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    snapshot = _snapshot(request)
    runtime_llm = request.app.state.runtime_llm
    return HealthResponse(
        status="ok",
        runtime_llm=runtime_llm.available,
        llm_provider=runtime_llm.provider if runtime_llm.available else "",
        llm_model=runtime_llm.model if runtime_llm.available else "",
        llm_configured=runtime_llm.configured,
        llm_endpoint_class=runtime_llm.endpoint_class,
        llm_protected_evidence_allowed=runtime_llm.protected_evidence_allowed,
        data_version=snapshot.data_version,
        graph_backend=snapshot.graph.backend_name,
        vector_backend=snapshot.vectors.backend_name,
        metadata_backend="sqlite",
    )


@router.post("/api/v1/qa/query", response_model=Answer)
def query_answer(payload: QARequest, request: Request) -> Answer:
    return _answer_for_mode(payload, request)


@router.post("/api/v1/triage/sessions", response_model=TriageSessionResponse)
def start_triage(request: Request) -> TriageSessionResponse:
    return _triage(request).start()


@router.get(
    "/api/v1/triage/sessions/{session_id}",
    response_model=TriageSessionResponse,
)
def get_triage(session_id: str, request: Request) -> TriageSessionResponse:
    response = _triage(request).get(session_id)
    if response is None:
        raise HTTPException(status_code=404, detail="triage session not found")
    return response


@router.post(
    "/api/v1/triage/sessions/{session_id}/answer",
    response_model=TriageSessionResponse,
)
def answer_triage(
    session_id: str,
    payload: TriageAnswerRequest,
    request: Request,
) -> TriageSessionResponse:
    try:
        response = _triage(request).answer(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if response is None:
        raise HTTPException(status_code=404, detail="triage session not found")
    return response


@router.post("/api/v1/qa/stream")
def stream_answer(payload: QARequest, request: Request) -> StreamingResponse:
    answer = _answer_for_mode(payload, request)

    def serialize(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        yield serialize(
            "status",
            {
                "stage": "retrieving",
                "message": "正在检索知识图谱与证据",
                "session_id": answer.session_id,
            },
        )
        yield serialize("intent", {"intent": answer.intent})
        if answer.safety_notice:
            yield serialize("safety", {"notice": answer.safety_notice})
        if answer.generation.configured:
            yield serialize(
                "generation",
                answer.generation.model_dump(mode="json"),
            )
        for claim in answer.claims:
            yield serialize("claim", claim.model_dump(mode="json"))
        for citation in answer.citations:
            yield serialize("evidence", citation.model_dump(mode="json"))
        for path in answer.graph_paths:
            yield serialize("graph_path", path.model_dump(mode="json"))
        yield serialize(
            "done",
            answer.model_dump(mode="json"),
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _answer_for_mode(payload: QARequest, request: Request) -> Answer:
    user = _optional_user(request)
    if payload.mode != QAMode.DOMAIN and not user:
        raise HTTPException(status_code=401, detail="research login required")
    answer = _runtime_qa(request).answer(
        payload.query,
        session_id=payload.session_id,
        mode=payload.mode,
        filters=payload.filters,
    )
    if user:
        _auth(request).audit_access(
            user.id,
            "qa_query",
            target=payload.mode.value,
            metadata={
                "question": payload.query[:300],
                "generation_status": answer.generation.status.value,
                "generation_used": answer.generation.used,
                "data_version": answer.data_version.version,
                "data_scope": answer.data_scope,
            },
        )
    _record_unmet_answer(request, answer)
    return answer


def _record_unmet_answer(request: Request, answer: Answer) -> None:
    if (
        answer.intent == "capabilities"
        or answer.sufficiency == EvidenceSufficiency.SUFFICIENT
        or answer.safety_notice
    ):
        return
    reason = (
        "partial_evidence"
        if answer.sufficiency == EvidenceSufficiency.PARTIAL
        else "evidence_insufficient"
    )
    detail = (
        f"自动记录：答案充分性为 {answer.sufficiency.value}；"
        f"已检索来源 {', '.join(answer.data_scope) or '未标记'}。"
    )
    _snapshot(request).metadata.record_unmet_need(
        session_id=answer.session_id,
        query=answer.query,
        mode=answer.mode.value,
        intent=answer.intent,
        reason=reason,
        detail=detail,
        data_scope=answer.data_scope,
        data_version=answer.data_version.version,
    )


@router.get("/api/v1/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=30),
    origin: str | None = Query(
        default=None,
        pattern="^(internal|external|public|all)$",
    ),
) -> SearchResponse:
    snapshot = _snapshot(request)
    user = _optional_user(request)
    if origin == "internal" and not user:
        raise HTTPException(status_code=401, detail="research login required")
    effective_origin = origin
    combined: dict[str, SearchResult] = {}
    expanded_query = _engine(request)._expanded_text_query(q) or q
    source_types = (
        _external_source_types()
        if not user and origin in {None, "all"}
        else _source_types_for_origin(effective_origin)
    )
    for row in snapshot.metadata.search_fts(
        expanded_query,
        limit=limit,
        source_types=source_types,
    ):
        if (
            effective_origin not in {None, "all"}
            and row["data_origin"] != effective_origin
        ):
            continue
        if not user and row["data_origin"] == "internal":
            continue
        score = 1.0 / (1.0 + abs(float(row["rank"] or 0.0)))
        evidence_json = _search_evidence_json(row)
        combined[row["id"]] = SearchResult(
            chunk_id=row["id"],
            document_id=row["document_id"],
            source_id=row["source_id"],
            title=row["title"],
            source_classification=row["source_classification"],
            data_origin=row["data_origin"],
            data_owner=row["data_owner"],
            access_scope=row["access_scope"],
            source_type=row["source_type"] or "",
            review_status=row["review_status"] or "",
            input_status=row["input_status"] or "",
            fusion_status=row["fusion_status"] or "",
            evidence_status=row["evidence_status"] or "",
            graph_display_role=row["graph_display_role"] or "",
            answer_eligible=bool(row["answer_eligible"]),
            source_record_id=row["source_record_id"] or "",
            source_version=row["source_version"] or "",
            source_locator=row["source_locator"] or "",
            url=row["url"] or "",
            predicate=str(evidence_json.get("predicate") or ""),
            snippet=row["text"][:360],
            entity_ids=json.loads(row["entity_ids_json"] or "[]"),
            evidence_json=evidence_json,
            score=score,
            is_demo=bool(row["is_demo"]),
        )

    vector_limit = limit * 4 if effective_origin not in {None, "all"} else limit
    for item in snapshot.vectors.search(expanded_query, limit=vector_limit):
        chunk_id = item["chunk_id"]
        vector_metadata = item.get("metadata") or {}
        if vector_metadata.get("kind") == "graph_summary":
            continue
        chunk = snapshot.metadata.get_chunk(chunk_id)
        if not chunk:
            continue
        if (
            effective_origin not in {None, "all"}
            and chunk["data_origin"] != effective_origin
        ):
            continue
        if not user and chunk["data_origin"] == "internal":
            continue
        previous = combined.get(chunk_id)
        score = float(item["score"])
        evidence_json = _search_evidence_json(chunk)
        combined[chunk_id] = SearchResult(
            chunk_id=chunk_id,
            document_id=chunk["document_id"],
            source_id=chunk["source_id"],
            title=chunk["title"],
            source_classification=chunk["source_classification"],
            data_origin=chunk["data_origin"],
            data_owner=chunk["data_owner"],
            access_scope=chunk["access_scope"],
            source_type=chunk["evidence_source_type"] or "",
            review_status=chunk["review_status"] or "",
            input_status=chunk["input_status"] or "",
            fusion_status=chunk["fusion_status"] or "",
            evidence_status=chunk["evidence_status"] or "",
            graph_display_role=chunk["graph_display_role"] or "",
            answer_eligible=bool(chunk["answer_eligible"]),
            source_record_id=chunk["source_record_id"] or "",
            source_version=chunk["source_version"] or "",
            source_locator=chunk["source_locator"] or "",
            url=chunk["url"] or "",
            predicate=str(evidence_json.get("predicate") or ""),
            snippet=chunk["text"][:360],
            entity_ids=json.loads(chunk["entity_ids_json"] or "[]"),
            evidence_json=evidence_json,
            score=max(score, previous.score if previous else 0.0),
            is_demo=bool(chunk["is_demo"]),
        )

    items = sorted(combined.values(), key=lambda item: item.score, reverse=True)[:limit]
    return SearchResponse(items=items, total=len(items))


@router.get("/api/v1/evidence/{evidence_id}")
def evidence(evidence_id: str, request: Request):
    row = _snapshot(request).metadata.get_evidence(evidence_id)
    if not row:
        raise HTTPException(status_code=404, detail="evidence not found")
    if row["data_origin"] == "internal" and not _optional_user(request):
        raise HTTPException(status_code=404, detail="evidence not found")
    evidence_json = _search_evidence_json(row)
    return {
        "evidence_json": evidence_json,
        **evidence_json,
        "id": row["id"],
        "source_id": row["source_id"],
        "source_title": row["title"],
        "source_type": row["source_type"],
        "source_classification": row["source_classification"],
        "data_origin": row["data_origin"],
        "data_owner": row["data_owner"],
        "access_scope": row["access_scope"],
        "publisher": row["publisher"],
        "published_at": row["published_at"],
        "url": row["url"],
        "evidence_level": row["evidence_level"],
        "locator": row["locator"],
        "snippet": row["chunk_text"],
        "is_demo": bool(row["is_demo"]),
    }


@router.get("/api/v1/research/overview", response_model=ResearchOverview)
def research_overview(request: Request) -> ResearchOverview:
    _require_user(request)
    return _research(request).overview()


@router.get("/api/v1/research/facets")
def research_facets(request: Request):
    _require_user(request)
    return _research(request).facets()


@router.get(
    "/api/v1/research/evidence",
    response_model=ResearchEvidenceResponse,
)
def research_evidence(
    request: Request,
    q: str = Query(default="", max_length=500),
    collection: str = Query(default="all", pattern="^(all|core|contextual)$"),
    test_family: str = Query(default="", max_length=80),
    outcome: str = Query(default="", max_length=120),
    evidence_level: str = Query(default="", max_length=40),
    result_status: str = Query(default="", max_length=80),
    review_status: str = Query(default="", max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResearchEvidenceResponse:
    _require_user(request)
    return _research(request).search(
        query=q,
        collection=collection,
        test_family=test_family,
        outcome=outcome,
        evidence_level=evidence_level,
        result_status=result_status,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/api/v1/research/insights",
    response_model=ResearchInsights,
)
def research_insights(request: Request) -> ResearchInsights:
    _require_user(request)
    return _research(request).insights()


@router.post(
    "/api/v1/feedback/unmet",
    response_model=UnmetNeedRecord,
)
def record_unmet_need(
    payload: UnmetNeedRequest,
    request: Request,
) -> UnmetNeedRecord:
    user = _optional_user(request)
    if payload.mode != QAMode.DOMAIN and not user:
        raise HTTPException(status_code=401, detail="research login required")
    if "internal" in payload.data_scope and not user:
        raise HTTPException(status_code=401, detail="research login required")
    record = _snapshot(request).metadata.record_unmet_need(
        session_id=payload.session_id,
        query=payload.query,
        mode=payload.mode.value,
        intent="",
        reason=payload.reason,
        detail=payload.detail,
        data_scope=payload.data_scope,
        data_version=_snapshot(request).version,
    )
    return UnmetNeedRecord(**record)


def _graph_scope(request: Request, scope: str) -> str:
    if scope not in {"domain", "research", "comparison"}:
        raise HTTPException(status_code=422, detail="invalid graph scope")
    if scope in {"research", "comparison"} and not _optional_user(request):
        raise HTTPException(status_code=401, detail="research login required")
    return scope


def _filter_graph_scope(
    request: Request,
    nodes,
    edges,
    scope: str,
):
    if scope == "comparison":
        return nodes, edges
    internal_rows = _snapshot(request).metadata.all_internal_evidence()
    internal_edge_ids = {str(row.get("edge_id") or "") for row in internal_rows}
    internal_evidence_ids = {str(row.get("id") or "") for row in internal_rows}

    def allowed(edge) -> bool:
        is_internal = (
            edge.id in internal_edge_ids
            or bool(internal_evidence_ids.intersection(edge.evidence_ids))
        )
        return is_internal if scope == "research" else not is_internal

    scoped_edges = [edge for edge in edges if allowed(edge)]
    node_ids = {
        node_id
        for edge in scoped_edges
        for node_id in (edge.source, edge.target)
    }
    scoped_nodes = [node for node in nodes if node.id in node_ids]
    return scoped_nodes, scoped_edges


@router.get("/api/v1/graph/search", response_model=GraphSearchResponse)
def graph_search(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="domain"),
) -> GraphSearchResponse:
    scope = _graph_scope(request, scope)
    snapshot = _snapshot(request)
    nodes, edges = _filter_graph_scope(
        request,
        snapshot.graph.all_nodes(),
        snapshot.graph.all_edges(),
        scope,
    )
    allowed_ids = {node.id for node in nodes}
    normalized_query = _engine(request).normalize(q)
    items = [
        node
        for node in snapshot.graph.search_nodes(normalized_query, limit=max(limit, 100))
        if node.id in allowed_ids
    ][:limit]
    return GraphSearchResponse(items=items, total=len(items))


@router.get("/api/v1/graph/meta")
def graph_meta(
    request: Request,
    scope: str = Query(default="domain"),
):
    scope = _graph_scope(request, scope)
    nodes, edges = _filter_graph_scope(
        request,
        _snapshot(request).graph.all_nodes(),
        _snapshot(request).graph.all_edges(),
        scope,
    )
    domains = sorted({node.domain for node in nodes})
    types = sorted({node.type for node in nodes})
    return {
        "domains": domains,
        "types": types,
        "stats": {"nodes": len(nodes), "edges": len(edges)},
        "data_version": _snapshot(request).data_version,
    }


@router.post("/api/v1/graph/full", response_model=SubgraphResponse)
def graph_full(payload: FullGraphRequest, request: Request) -> SubgraphResponse:
    scope = _graph_scope(request, payload.scope)
    if scope == "research":
        raise HTTPException(
            status_code=400,
            detail="research graph only supports focus subgraphs",
        )
    snapshot = _snapshot(request)
    domains = set(payload.domains)
    nodes = [
        node for node in snapshot.graph.all_nodes() if not domains or node.domain in domains
    ]
    node_ids = {node.id for node in nodes}
    edges = [
        edge
        for edge in snapshot.graph.all_edges()
        if edge.source in node_ids and edge.target in node_ids
    ]
    nodes, edges = _filter_graph_scope(request, nodes, edges, scope)
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        data_version=snapshot.data_version,
    )


@router.post("/api/v1/graph/subgraph", response_model=SubgraphResponse)
def graph_subgraph(payload: SubgraphRequest, request: Request) -> SubgraphResponse:
    scope = _graph_scope(request, payload.scope)
    nodes, edges = _snapshot(request).graph.subgraph(
        payload.entity_ids,
        depth=payload.depth,
        domains=set(payload.domains) or None,
        limit=payload.limit,
    )
    nodes, edges = _filter_graph_scope(request, nodes, edges, scope)
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        data_version=_snapshot(request).data_version,
    )


@router.post("/internal/v1/ingest", response_model=IngestResponse)
def ingest(
    payload: IngestRequest,
    request: Request,
) -> IngestResponse:
    _require_admin(request)
    service = IngestionService(request.app.state.settings, _manager(request))
    result = service.ingest(
        Path(payload.path).expanduser().resolve(),
        source_title=payload.source_title,
        source_type=payload.source_type,
        data_origin=payload.data_origin.value,
        data_owner=payload.data_owner,
        access_scope=payload.access_scope.value,
        source_classification=payload.source_classification,
        use_llm=payload.use_llm,
        activate=payload.activate,
    )
    return IngestResponse(**result)


@router.post(
    "/internal/v1/import-external-triples",
    response_model=ExternalTripleImportResponse,
)
def import_external_triples(
    payload: ExternalTripleImportRequest,
    request: Request,
) -> ExternalTripleImportResponse:
    _require_admin(request)
    importer = ExternalTripleImporter(_manager(request))
    result = importer.import_csv(
        Path(payload.path).expanduser().resolve(),
        data_owner=payload.data_owner,
        activate=payload.activate,
    )
    return ExternalTripleImportResponse(**result)


@router.post(
    "/internal/v1/upload-external-triples",
)
async def upload_external_triples(
    request: Request,
    file: Annotated[UploadFile, File()],
    data_owner: str = Form(default="已发表维生素 K 研究文献"),
    activate: bool = Form(default=False),
) -> dict:
    _require_admin(request)
    return await _import_uploaded_evidence_table(
        request,
        file,
        activate=activate,
    )


@router.post("/internal/v1/upload-internal-csv")
async def upload_internal_csv(
    request: Request,
    file: Annotated[UploadFile, File()],
    data_owner: str = Form(default="毕业设计内部资料"),
    source_type: str = Form(default="rct"),
    source_classification: str = Form(default="internal_rct"),
    activate: bool = Form(default=False),
) -> IngestResponse:
    _require_admin(request)
    return await _import_uploaded_evidence_table(
        request,
        file,
        activate=activate,
    )


async def _import_uploaded_evidence_table(
    request: Request,
    file: UploadFile,
    *,
    activate: bool,
) -> dict:
    output_dir = request.app.state.settings.runtime_dir / "uploads"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "evidence.csv").suffix or ".csv"
    upload_path = output_dir / f"evidence-{uuid.uuid4().hex}{suffix}"
    upload_path.write_bytes(await file.read())
    version = f"upload-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    try:
        result = EvidenceTableImporter(_manager(request)).import_files(
            [upload_path],
            version=version,
            activate=activate,
        )
    finally:
        upload_path.unlink(missing_ok=True)
    return result


@router.post("/internal/v1/import-evidence-tables")
def import_evidence_tables(
    payload: EvidenceTableImportRequest,
    request: Request,
):
    _require_admin(request)
    result = EvidenceTableImporter(_manager(request)).import_files(
        [Path(path).expanduser().resolve() for path in payload.paths],
        version=payload.version,
        activate=payload.activate,
        build_vectors=payload.build_vectors,
    )
    return result


@router.get("/internal/v1/review")
def review_items(
    request: Request,
    status: str = Query(default="pending", max_length=40),
):
    _require_admin(request)
    return {"items": _snapshot(request).metadata.list_review_items(status)}


@router.post("/internal/v1/review")
def review_decide(
    payload: ReviewDecisionRequest,
    request: Request,
):
    _require_admin(request)
    service = IngestionService(request.app.state.settings, _manager(request))
    count = service.apply_review(
        _snapshot(request),
        payload.candidate_ids,
        payload.decision,
        payload.reviewer,
    )
    return {"updated": count}


@router.post("/internal/v1/snapshots/{version}/activate")
def activate_snapshot(
    version: str,
    request: Request,
):
    _require_admin(request)
    version = _known_snapshot_version(request, version)
    if request.app.state.snapshot.version == version:
        return {"version": version, "status": "already-active"}
    request.app.state.snapshot.close()
    payload = _manager(request).activate(version)
    snapshot = _manager(request).open(version)
    engine = _engine(request)
    engine.snapshot = snapshot
    engine.metadata = snapshot.metadata
    engine.graph = snapshot.graph
    engine.vectors = snapshot.vectors
    request.app.state.snapshot = snapshot
    request.app.state.triage.rebind(snapshot)
    return payload


@router.get("/internal/v1/snapshots")
def snapshots(
    request: Request,
):
    _require_admin(request)
    return {"items": _manager(request).list()}


@router.get(
    "/internal/v1/governance/active",
    response_model=SnapshotAudit,
)
def active_snapshot_audit(request: Request) -> SnapshotAudit:
    _require_admin(request)
    return _manager(request).audit(_snapshot(request).version)


@router.get(
    "/internal/v1/governance/snapshots/{version}",
    response_model=SnapshotAudit,
)
def snapshot_audit(
    version: str,
    request: Request,
) -> SnapshotAudit:
    _require_admin(request)
    version = _known_snapshot_version(request, version)
    return _manager(request).audit(version)


@router.get(
    "/internal/v1/governance/diff",
    response_model=SnapshotDiff,
)
def snapshot_diff(
    request: Request,
    from_version: str = Query(min_length=1, max_length=160),
    to_version: str = Query(min_length=1, max_length=160),
) -> SnapshotDiff:
    _require_admin(request)
    from_version = _known_snapshot_version(request, from_version)
    to_version = _known_snapshot_version(request, to_version)
    return _manager(request).diff(from_version, to_version)


@router.get("/internal/v1/audit-logs")
def audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
):
    _require_admin(request)
    return {"items": _auth(request).audit_log(limit)}


@router.get("/internal/v1/unmet-needs", response_model=UnmetNeedsResponse)
def unmet_needs(
    request: Request,
    status: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
) -> UnmetNeedsResponse:
    _require_admin(request)
    items = _snapshot(request).metadata.list_unmet_needs(
        status=status,
        limit=limit,
    )
    return UnmetNeedsResponse(
        items=[UnmetNeedRecord(**item) for item in items],
        total=len(items),
    )
