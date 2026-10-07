from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.qa import GraphAnswerEngine
from app.services.snapshot import SnapshotManager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = SnapshotManager(settings)
    snapshot = manager.bootstrap()
    app.state.settings = settings
    app.state.snapshot_manager = manager
    app.state.snapshot = snapshot
    app.state.engine = GraphAnswerEngine(settings, snapshot)
    yield
    snapshot.close()


app = FastAPI(
    title="VitaK-RAG API",
    version="0.1.0",
    description="Deterministic graph-grounded vitamin K question answering prototype.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "VitaK-RAG",
        "runtime_llm": False,
        "docs": "/docs",
        "health": "/api/v1/health",
    }

