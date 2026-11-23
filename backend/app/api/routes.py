from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas import (
    Answer,
    EvidenceTableImportRequest,
    ExternalTripleImportRequest,
    ExternalTripleImportResponse,
    FullGraphRequest,
    GraphSearchResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QARequest,
    ReviewDecisionRequest,
    SearchResponse,
    SearchResult,
    SubgraphRequest,
    SubgraphResponse,
)
from app.services.evidence_tables import EvidenceTableImporter
from app.services.external_triples import ExternalTripleImporter
from app.services.ingest import IngestionService

router = APIRouter()


def _engine(request: Request):
    return request.app.state.engine


def _snapshot(request: Request):
    return request.app.state.snapshot


def _manager(request: Request):
    return request.app.state.snapshot_manager


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


def _assert_internal_token(request: Request, token: str | None) -> None:
    expected = request.app.state.settings.internal_token
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="invalid internal token")
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="internal API is localhost-only")


@router.get("/api/v1/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    snapshot = _snapshot(request)
    return HealthResponse(
        status="ok",
        runtime_llm=False,
        data_version=snapshot.data_version,
        graph_backend=snapshot.graph.backend_name,
        vector_backend=snapshot.vectors.backend_name,
        metadata_backend="sqlite",
    )


@router.post("/api/v1/qa/query", response_model=Answer)
def query_answer(payload: QARequest, request: Request) -> Answer:
    return _engine(request).answer(payload.query, payload.session_id)


@router.post("/api/v1/qa/stream")
def stream_answer(payload: QARequest, request: Request) -> StreamingResponse:
    answer = _engine(request).answer(payload.query, payload.session_id)

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


@router.get("/api/v1/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=30),
) -> SearchResponse:
    snapshot = _snapshot(request)
    combined: dict[str, SearchResult] = {}
    expanded_query = _engine(request)._expanded_text_query(q) or q
    for row in snapshot.metadata.search_fts(expanded_query, limit=limit):
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

    for item in snapshot.vectors.search(expanded_query, limit=limit):
        chunk_id = item["chunk_id"]
        vector_metadata = item.get("metadata") or {}
        if vector_metadata.get("kind") == "graph_summary":
            continue
        chunk = snapshot.metadata.get_chunk(chunk_id)
        if not chunk:
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


@router.get("/api/v1/graph/search", response_model=GraphSearchResponse)
def graph_search(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> GraphSearchResponse:
    items = _snapshot(request).graph.search_nodes(q, limit=limit)
    return GraphSearchResponse(items=items, total=len(items))


@router.get("/api/v1/graph/meta")
def graph_meta(request: Request):
    nodes = _snapshot(request).graph.all_nodes()
    domains = sorted({node.domain for node in nodes})
    types = sorted({node.type for node in nodes})
    return {
        "domains": domains,
        "types": types,
        "stats": _snapshot(request).graph.stats(),
        "data_version": _snapshot(request).data_version,
    }


@router.post("/api/v1/graph/full", response_model=SubgraphResponse)
def graph_full(payload: FullGraphRequest, request: Request) -> SubgraphResponse:
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
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        data_version=snapshot.data_version,
    )


@router.post("/api/v1/graph/subgraph", response_model=SubgraphResponse)
def graph_subgraph(payload: SubgraphRequest, request: Request) -> SubgraphResponse:
    nodes, edges = _snapshot(request).graph.subgraph(
        payload.entity_ids,
        depth=payload.depth,
        domains=set(payload.domains) or None,
        limit=payload.limit,
    )
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        data_version=_snapshot(request).data_version,
    )


@router.post("/internal/v1/ingest", response_model=IngestResponse)
def ingest(
    payload: IngestRequest,
    request: Request,
    x_internal_token: str | None = Header(default=None),
) -> IngestResponse:
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
) -> ExternalTripleImportResponse:
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
) -> dict:
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
) -> IngestResponse:
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
):
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
):
    _assert_internal_token(request, x_internal_token)
    return {"items": _snapshot(request).metadata.list_review_items("pending")}


@router.post("/internal/v1/review")
def review_decide(
    payload: ReviewDecisionRequest,
    request: Request,
    x_internal_token: str | None = Header(default=None),
):
    _assert_internal_token(request, x_internal_token)
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
    x_internal_token: str | None = Header(default=None),
):
    _assert_internal_token(request, x_internal_token)
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
    return payload


@router.get("/internal/v1/snapshots")
def snapshots(
    request: Request,
    x_internal_token: str | None = Header(default=None),
):
    _assert_internal_token(request, x_internal_token)
    return {"items": _manager(request).list()}
