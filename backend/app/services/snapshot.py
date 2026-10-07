from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas import DataVersion
from app.services.seed import seed_demo_snapshot
from app.storage.database import MetadataStore
from app.storage.graph import KuzuGraphStore
from app.storage.vector import ChromaVectorStore

DEMO_VERSION = "demo-2026.10.2"


@dataclass
class SnapshotContext:
    version: str
    root: Path
    manifest: dict[str, Any]
    metadata: MetadataStore
    graph: KuzuGraphStore
    vectors: ChromaVectorStore

    @property
    def data_version(self) -> DataVersion:
        return DataVersion(**self.manifest)

    def close(self) -> None:
        database = getattr(self.graph, "database", None)
        if database and hasattr(database, "close"):
            database.close()


class SnapshotManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def bootstrap(self) -> SnapshotContext:
        if not self.settings.active_manifest.exists():
            self.create_demo_snapshot()
            self.activate(DEMO_VERSION)
        try:
            return self.open_active()
        except (KeyError, FileNotFoundError, RuntimeError):
            self.create_demo_snapshot()
            self.activate(DEMO_VERSION)
            return self.open_active()

    def create_demo_snapshot(self) -> None:
        root = self.settings.snapshots_dir / DEMO_VERSION
        root.mkdir(parents=True, exist_ok=True)
        metadata = MetadataStore(root / "metadata.sqlite3")
        graph = KuzuGraphStore(root / "graph.kuzu")
        vectors = ChromaVectorStore(root / "vectors")
        counts = seed_demo_snapshot(metadata, graph, vectors)
        counts.update(
            {
                "entity_count": counts["nodes"],
                "relation_count": counts["edges"],
                "source_count": counts["sources"],
                "chunk_count": counts["chunks"],
            }
        )
        manifest = {
            "version": DEMO_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "is_demo": True,
            "entity_count": counts["nodes"],
            "relation_count": counts["edges"],
            "source_count": counts["sources"],
            "chunk_count": counts["chunks"],
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metadata.add_snapshot(DEMO_VERSION, str(root), "ready", True)
        graph.database.close()

    def open(self, version: str) -> SnapshotContext:
        root = self.settings.snapshots_dir / version
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"snapshot manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = MetadataStore(root / "metadata.sqlite3")
        metadata.initialize()
        graph = KuzuGraphStore(root / "graph.kuzu")
        graph.initialize()
        vectors = ChromaVectorStore(root / "vectors")
        return SnapshotContext(version, root, manifest, metadata, graph, vectors)

    def open_active(self) -> SnapshotContext:
        if not self.settings.active_manifest.exists():
            raise FileNotFoundError("no active snapshot")
        payload = json.loads(self.settings.active_manifest.read_text(encoding="utf-8"))
        return self.open(payload["version"])

    def activate(self, version: str) -> dict[str, Any]:
        root = self.settings.snapshots_dir / version
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"snapshot not found: {version}")
        payload = {
            "version": version,
            "path": str(root),
            "activated_at": datetime.now(UTC).isoformat(),
        }
        temporary = self.settings.active_manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.settings.active_manifest)

        metadata = MetadataStore(root / "metadata.sqlite3")
        metadata.initialize()
        metadata.mark_snapshot_active(version)
        return payload

    def list(self) -> list[dict[str, Any]]:
        output = []
        for manifest_path in sorted(self.settings.snapshots_dir.glob("*/manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["path"] = str(manifest_path.parent)
            output.append(manifest)
        return output

    def validate(self, version: str) -> dict[str, Any]:
        context = self.open(version)
        try:
            counts = context.metadata.counts()
            graph_counts = context.graph.stats()
            errors = []
            if counts["sources"] <= 0:
                errors.append("no sources")
            if counts["chunks"] <= 0:
                errors.append("no chunks")
            if graph_counts["nodes"] <= 0:
                errors.append("no graph nodes")
            if graph_counts["edges"] <= 0:
                errors.append("no graph edges")
            return {
                "valid": not errors,
                "version": version,
                "errors": errors,
                "counts": {**counts, **graph_counts},
            }
        finally:
            context.close()

    def create_derived_snapshot(
        self,
        base_version: str,
        prefix: str = "import",
    ) -> SnapshotContext:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        version = f"{prefix}-{timestamp}-{uuid.uuid4().hex[:6]}"
        source = self.settings.snapshots_dir / base_version
        target = self.settings.snapshots_dir / version
        if not source.exists():
            raise FileNotFoundError(f"base snapshot not found: {base_version}")
        shutil.copytree(source, target)
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = version
        manifest["created_at"] = datetime.now(UTC).isoformat()
        manifest["is_demo"] = False
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metadata = MetadataStore(target / "metadata.sqlite3")
        metadata.initialize()
        metadata.add_snapshot(version, str(target), "staged", False)
        return self.open(version)
