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
from app.schemas import DataVersion, GovernanceCheck, SnapshotAudit, SnapshotDiff
from app.services.seed import seed_demo_snapshot
from app.storage.database import MetadataStore
from app.storage.graph import KuzuGraphStore
from app.storage.vector import ChromaVectorStore

DEMO_VERSION = "demo-2026.10.4"


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
        except FileNotFoundError:
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

    def create_empty_snapshot(
        self,
        version: str,
        *,
        is_demo: bool = False,
    ) -> SnapshotContext:
        root = self.settings.snapshots_dir / version
        if root.exists():
            raise FileExistsError(f"snapshot already exists: {root}")
        root.mkdir(parents=True)
        metadata = MetadataStore(root / "metadata.sqlite3")
        metadata.initialize()
        graph = KuzuGraphStore(root / "graph.kuzu")
        graph.initialize()
        ChromaVectorStore(root / "vectors")
        manifest = {
            "version": version,
            "created_at": datetime.now(UTC).isoformat(),
            "is_demo": is_demo,
            "entity_count": 0,
            "relation_count": 0,
            "source_count": 0,
            "chunk_count": 0,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metadata.add_snapshot(version, str(root), "staged", is_demo)
        graph.database.close()
        return self.open(version)

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

    def _active_version(self) -> str:
        if not self.settings.active_manifest.exists():
            return ""
        try:
            payload = json.loads(self.settings.active_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        return str(payload.get("version") or "")

    def audit(self, version: str) -> SnapshotAudit:
        root = self.settings.snapshots_dir / version
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"snapshot manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = MetadataStore(root / "metadata.sqlite3")
        metadata.initialize()
        try:
            counts = metadata.counts()
            graph_counts = {
                "nodes": int(manifest.get("entity_count", 0)),
                "edges": int(manifest.get("relation_count", 0)),
            }
            stats = manifest.get("import_stats") or {}
            with metadata.connect() as connection:
                source_types = {
                    str(row["value"]): int(row["count"])
                    for row in connection.execute(
                        "SELECT source_type AS value, COUNT(*) AS count "
                        "FROM sources GROUP BY source_type"
                    ).fetchall()
                }
                origins = {
                    str(row["value"]): int(row["count"])
                    for row in connection.execute(
                        "SELECT data_origin AS value, COUNT(*) AS count "
                        "FROM sources GROUP BY data_origin"
                    ).fetchall()
                }
                access_scopes = {
                    str(row["value"]): int(row["count"])
                    for row in connection.execute(
                        "SELECT access_scope AS value, COUNT(*) AS count "
                        "FROM sources GROUP BY access_scope"
                    ).fetchall()
                }
                review_statuses = {
                    str(row["value"] or "未标记"): int(row["count"])
                    for row in connection.execute(
                        "SELECT review_status AS value, COUNT(*) AS count "
                        "FROM evidence GROUP BY review_status"
                    ).fetchall()
                }
                evidence_statuses = {
                    str(row["value"] or "未标记"): int(row["count"])
                    for row in connection.execute(
                        "SELECT evidence_status AS value, COUNT(*) AS count "
                        "FROM evidence GROUP BY evidence_status"
                    ).fetchall()
                }
                internal_permission_leaks = connection.execute(
                    "SELECT COUNT(*) FROM sources "
                    "WHERE data_origin = 'internal' AND access_scope != 'private'"
                ).fetchone()[0]
                input_files = [
                    {
                        "name": Path(str(row["file"])).name or "未记录文件",
                        "sha256": str(row["sha256"] or ""),
                        "rows": int(row["count"]),
                    }
                    for row in connection.execute(
                        """
                        SELECT
                            json_extract(e.metadata_json, '$.source_file') AS file,
                            json_extract(e.metadata_json, '$.input_file_sha256') AS sha256,
                            COUNT(*) AS count
                        FROM evidence e
                        JOIN sources s ON s.id = e.source_id
                        WHERE s.data_origin = 'internal'
                        GROUP BY file, sha256
                        ORDER BY file
                        """
                    ).fetchall()
                ]

            duplicate_edges = int(stats.get("duplicate_edge_ids", 0))
            missing_required = int(stats.get("missing_required", 0))
            node_conflicts = int(stats.get("node_conflicts", 0))
            dangling_edges = int(stats.get("dangling_graph_edges", -1))
            checks = [
                GovernanceCheck(
                    key="duplicate_ids",
                    label="重复边 ID",
                    status="pass" if duplicate_edges == 0 else "fail",
                    value=duplicate_edges,
                    detail="冻结导入记录中的 edge_id 唯一性检查。",
                ),
                GovernanceCheck(
                    key="missing_required",
                    label="必填字段缺失",
                    status="pass" if missing_required == 0 else "fail",
                    value=missing_required,
                    detail="缺失记录未静默删除，导入统计保留计数。",
                ),
                GovernanceCheck(
                    key="node_conflicts",
                    label="实体标签/类型冲突",
                    status="pass" if node_conflicts == 0 else "warn",
                    value=node_conflicts,
                    detail="冲突需要科研方审核语义后决定，不自动改写。",
                ),
                GovernanceCheck(
                    key="dangling_edges",
                    label="悬空端点",
                    status="pass" if dangling_edges == 0 else "unavailable",
                    value=dangling_edges if dangling_edges >= 0 else "未持久化",
                    detail=(
                        "当前快照未保存逐边悬空检查清单，不能将缺失报告解释为零。"
                        if dangling_edges < 0
                        else "导入清单记录的悬空端点数。"
                    ),
                ),
                GovernanceCheck(
                    key="internal_permissions",
                    label="内部数据权限",
                    status="pass" if internal_permission_leaks == 0 else "fail",
                    value=int(internal_permission_leaks),
                    detail="internal 来源必须使用 private 访问范围。",
                ),
            ]
            return SnapshotAudit(
                version=version,
                created_at=str(manifest.get("created_at") or ""),
                is_demo=bool(manifest.get("is_demo")),
                active=version == self._active_version(),
                counts={**counts, **graph_counts},
                source_types=source_types,
                origins=origins,
                access_scopes=access_scopes,
                review_statuses=review_statuses,
                evidence_statuses=evidence_statuses,
                checks=checks,
                warnings=[str(item) for item in stats.get("warnings", [])],
                input_files=input_files,
            )
        except Exception:
            raise

    def diff(self, from_version: str, to_version: str) -> SnapshotDiff:
        from_manifest = json.loads(
            (self.settings.snapshots_dir / from_version / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        to_manifest = json.loads(
            (self.settings.snapshots_dir / to_version / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        from_stats = from_manifest.get("import_stats") or {}
        to_stats = to_manifest.get("import_stats") or {}
        count_keys = {
            "entity_count",
            "relation_count",
            "source_count",
            "chunk_count",
            "rows",
            "graph_edges",
            "skipped_graph_edges",
            "nodes",
            "literal_nodes",
            "sources",
            "documents",
            "chunks",
            "vectors",
            "answer_eligible",
            "answer_ineligible",
        }
        count_deltas = {}
        for key in sorted(count_keys):
            before = from_stats.get(key, from_manifest.get(key, 0))
            after = to_stats.get(key, to_manifest.get(key, 0))
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                count_deltas[key] = int(after - before)

        distribution_deltas = {}
        for key in (
            "source_types",
            "origins",
            "review_statuses",
            "input_statuses",
            "fusion_statuses",
            "evidence_statuses",
        ):
            before = from_stats.get(key) or {}
            after = to_stats.get(key) or {}
            values = sorted(set(before) | set(after))
            deltas = {
                value: int(after.get(value, 0) - before.get(value, 0))
                for value in values
                if after.get(value, 0) != before.get(value, 0)
            }
            if deltas:
                distribution_deltas[key] = deltas

        before_files = {
            Path(str(path)).name
            for path in from_stats.get("files", [])
            if str(path).strip()
        }
        after_files = {
            Path(str(path)).name
            for path in to_stats.get("files", [])
            if str(path).strip()
        }
        return SnapshotDiff(
            from_version=from_version,
            to_version=to_version,
            count_deltas=count_deltas,
            distribution_deltas=distribution_deltas,
            added_input_files=sorted(after_files - before_files),
            removed_input_files=sorted(before_files - after_files),
        )

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

    def clone_snapshot(
        self,
        base_version: str,
        version: str,
        *,
        activate: bool = False,
    ) -> SnapshotContext:
        source = self.settings.snapshots_dir / base_version
        target = self.settings.snapshots_dir / version
        if not (source / "manifest.json").exists():
            raise FileNotFoundError(f"base snapshot not found: {base_version}")
        if target.exists():
            raise FileExistsError(f"snapshot already exists: {target}")
        shutil.copytree(source, target)
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = version
        manifest["created_at"] = datetime.now(UTC).isoformat()
        manifest["derived_from"] = base_version
        manifest["is_demo"] = False
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metadata = MetadataStore(target / "metadata.sqlite3")
        metadata.initialize()
        metadata.add_snapshot(version, str(target), "ready", False)
        if activate:
            self.activate(version)
        return self.open(version)
