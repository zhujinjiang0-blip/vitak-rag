from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas import Citation
from app.services.snapshot import SnapshotContext


class StaticExportService:
    def __init__(self, snapshot: SnapshotContext):
        self.snapshot = snapshot

    def export(self, output: Path) -> dict[str, Any]:
        evidence = []
        for row in self.snapshot.metadata.all_evidence():
            citation = Citation(
                id=row["id"],
                source_id=row["source_id"],
                source_title=row["title"],
                source_type=row["source_type"],
                source_classification=row["source_classification"],
                data_origin=row["data_origin"],
                data_owner=row["data_owner"],
                access_scope=row["access_scope"],
                publisher=row["publisher"],
                published_at=row["published_at"],
                url=row["url"],
                evidence_level=row["evidence_level"],
                locator=row["locator"],
                snippet=row["chunk_text"],
                is_demo=bool(row["is_demo"]),
            )
            item = citation.model_dump(mode="json")
            item["document_id"] = row["chunk_id"]
            item["entity_ids"] = json.loads(row["entity_ids_json"] or "[]")
            evidence.append(item)

        payload = {
            "version": self.snapshot.data_version.model_dump(mode="json"),
            "nodes": [
                node.model_dump(mode="json") for node in self.snapshot.graph.all_nodes()
            ],
            "edges": [
                edge.model_dump(mode="json") for edge in self.snapshot.graph.all_edges()
            ],
            "evidence": evidence,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return {
            "output": str(output),
            "version": self.snapshot.version,
            "nodes": len(payload["nodes"]),
            "edges": len(payload["edges"]),
            "evidence": len(evidence),
            "bytes": output.stat().st_size,
        }
