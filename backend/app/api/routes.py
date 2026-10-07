from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import (
    Answer,
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
from app.services.ingest import IngestionService

router = APIRouter()


def _engine(request: Request):
    return request.app.state.engine


def _snapshot(request: Request):
    return request.app.state.snapshot


def _manager(request: Request):
    return request.app.state.snapshot_manager


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
    for row in snapshot.metadata.search_fts(q, limit=limit):
        score = 1.0 / (1.0 + abs(float(row["rank"] or 0.0)))
        combined[row["id"]] = SearchResult(
            chunk_id=row["id"],
            document_id=row["document_id"],
            source_id=row["source_id"],
            title=row["title"],
            snippet=row["text"][:360],
            entity_ids=json.loads(row["entity_ids_json"] or "[]"),
            score=score,
            is_demo=bool(row["is_demo"]),
        )

    for item in snapshot.vectors.search(q, limit=limit):
        chunk_id = item["chunk_id"]
        if not chunk_id.startswith(("src-", "pub-", "rct-demo-")):
            continue
        vector_metadata = item.get("metadata") or {}
        if vector_metadata.get("kind") == "graph_summary":
            continue
        chunk = snapshot.metadata.get_chunk(chunk_id)
        if not chunk:
            continue
        previous = combined.get(chunk_id)
        score = float(item["score"])
        combined[chunk_id] = SearchResult(
            chunk_id=chunk_id,
            document_id=chunk["document_id"],
            source_id=chunk["source_id"],
            title=chunk["title"],
            snippet=chunk["text"][:360],
            entity_ids=json.loads(chunk["entity_ids_json"] or "[]"),
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
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "source_title": row["title"],
        "source_type": row["source_type"],
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
        use_llm=payload.use_llm,
        activate=payload.activate,
    )
    return IngestResponse(**result)


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

