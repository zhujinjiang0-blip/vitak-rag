from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.auth import AuthStore
from app.services.qa import GraphAnswerEngine
from app.services.runtime_llm import RuntimeLLMClient
from app.services.snapshot import SnapshotManager
from app.services.triage import TriageService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = SnapshotManager(settings)
    research_root = settings.snapshots_dir / settings.research_snapshot_version
    if (research_root / "manifest.json").exists():
        snapshot = manager.open(settings.research_snapshot_version)
    else:
        snapshot = manager.bootstrap()
    auth = AuthStore(settings.resolved_auth_db_path, settings.session_ttl_hours)
    app.state.settings = settings
    app.state.snapshot_manager = manager
    app.state.snapshot = snapshot
    app.state.engine = GraphAnswerEngine(settings, snapshot)
    app.state.auth = auth
    app.state.runtime_llm = RuntimeLLMClient(settings)
    app.state.triage = TriageService(settings, snapshot)
    yield
    snapshot.close()


app = FastAPI(
    title="VitaK-RAG API",
    version="0.1.0",
    description=(
        "Evidence-constrained vitamin K question answering with deterministic fallback."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    runtime_llm = RuntimeLLMClient(settings)
    return {
        "name": "VitaK-RAG",
        "runtime_llm": runtime_llm.available,
        "llm_provider": runtime_llm.provider if runtime_llm.available else "",
        "llm_model": runtime_llm.model if runtime_llm.available else "",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
