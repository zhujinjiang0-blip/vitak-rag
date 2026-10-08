from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.schemas import GraphEdge, GraphNode
from app.services.snapshot import SnapshotContext, SnapshotManager
from app.storage.database import tokenize, utc_now

REQUIRED_COLUMNS = {
    "record_id",
    "pmid",
    "subject",
    "subject_normalized",
    "subject_matched_class",
    "subject_match_type",
    "predicate",
    "object",
    "object_normalized",
    "object_matched_class",
    "object_match_type",
    "source_sentence",
    "evidence_score",
    "evidence_grade",
    "confidence_score",
    "confidence_grade",
}


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def class_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return "ExternalEntity"
    for separator in ("#", "/", ":"):
        if separator in cleaned:
            cleaned = cleaned.rsplit(separator, 1)[-1]
    return cleaned or "ExternalEntity"


def domain_for_class(value: str) -> str:
    lowered = (value or "").lower()
    if any(term in lowered for term in ("food", "nutrient", "diet", "vitamin")):
        return "食物营养"
    if any(term in lowered for term in ("drug", "medication", "anticoagulant")):
        return "药物相互作用"
    if any(term in lowered for term in ("disease", "disorder", "condition", "symptom")):
        return "临床疾病"
    if any(term in lowered for term in ("assay", "test", "biomarker", "measure")):
        return "检测评估"
    if any(term in lowered for term in ("study", "trial", "guideline", "outcome")):
        return "指南与RCT"
    return "外部文献证据"


def confidence_value(value: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, number / 100 if number > 1 else number))


class ExternalTripleImporter:
    """Import the aligned external-literature triple table without re-extraction."""

    def __init__(self, manager: SnapshotManager):
        self.manager = manager

    def import_csv(
        self,
        csv_path: Path,
        *,
        data_owner: str = "已发表维生素 K 研究文献",
        activate: bool = False,
        batch_size: int = 1000,
    ) -> dict[str, Any]:
        if not csv_path.exists() or not csv_path.is_file():
            raise FileNotFoundError(f"aligned triples file not found: {csv_path}")

        current = self.manager.bootstrap()
        base_version = current.version
        current.close()
        snapshot = self.manager.create_derived_snapshot(base_version, prefix="external")
        warnings: list[str] = []
        imported_rows = 0
        skipped_rows = 0
        touched_nodes: dict[str, GraphNode] = {}
        touched_edges: list[tuple[int, GraphEdge]] = []
        source_rows: dict[str, dict[str, str]] = {}
        document_rows: dict[str, dict[str, str]] = {}
        chunk_rows: list[dict[str, str]] = []

        try:
            with csv_path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
                reader = csv.DictReader(handle)
                columns = set(reader.fieldnames or [])
                missing = sorted(REQUIRED_COLUMNS - columns)
                if missing:
                    raise ValueError(
                        "aligned_triples.csv 缺少字段: " + ", ".join(missing)
                    )

                for row_index, row in enumerate(reader, start=2):
                    subject_name = (row["subject_normalized"] or row["subject"]).strip()
                    object_name = (row["object_normalized"] or row["object"]).strip()
                    predicate = row["predicate"].strip()
                    if not subject_name or not object_name or not predicate:
                        skipped_rows += 1
                        warnings.append(f"第 {row_index} 行缺少主语、宾语或关系，已跳过。")
                        continue

                    subject_class = class_name(row["subject_matched_class"])
                    object_class = class_name(row["object_matched_class"])
                    subject_id = stable_id("EXT-NODE", subject_class, subject_name)
                    object_id = stable_id("EXT-NODE", object_class, object_name)
                    record_id = row["record_id"].strip() or stable_id("ROW", str(row_index))
                    pmid = row["pmid"].strip()
                    source_id = f"EXT-SRC-{record_id}"
                    document_id = f"EXT-DOC-{record_id}"
                    chunk_id = f"EXT-CHUNK-{record_id}-{row_index:06d}"
                    evidence_id = f"EXT-EV-{record_id}-{row_index:06d}"
                    edge_id = f"EXT-EDGE-{record_id}-{row_index:06d}"
                    source_title = (
                        f"已发表研究 PMID {pmid}"
                        if pmid
                        else f"已发表研究记录 {record_id}"
                    )

                    source_rows.setdefault(
                        source_id,
                        {
                            "source_id": source_id,
                            "title": source_title,
                            "source_type": "research_article",
                            "publisher": data_owner,
                            "published_at": "",
                            "url": (
                                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                                if pmid
                                else ""
                            ),
                            "metadata_json": json.dumps(
                                {
                                    "record_id": record_id,
                                    "pmid": pmid,
                                    "source_file": str(csv_path),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
                    document_rows.setdefault(
                        document_id,
                        {
                            "document_id": document_id,
                            "source_id": source_id,
                            "title": source_title,
                            "content_type": "text/csv",
                            "checksum": source_id,
                        },
                    )
                    chunk_rows.append(
                        {
                            "chunk_id": chunk_id,
                            "document_id": document_id,
                            "source_id": source_id,
                            "locator": f"aligned_triples.csv 第 {row_index} 行",
                            "text": row["source_sentence"].strip()
                            or f"{subject_name} {predicate} {object_name}",
                            "evidence_id": evidence_id,
                            "claim": row["source_sentence"].strip()
                            or f"{subject_name} {predicate} {object_name}",
                            "evidence_level": row["evidence_grade"].strip()
                            or "unclassified",
                            "confidence": confidence_value(row["confidence_score"]),
                            "metadata_json": json.dumps(
                                {
                                    "record_id": record_id,
                                    "pmid": pmid,
                                    "subject_match_type": row["subject_match_type"],
                                    "object_match_type": row["object_match_type"],
                                    "subject_matched_class": row["subject_matched_class"],
                                    "object_matched_class": row["object_matched_class"],
                                    "evidence_score": row["evidence_score"],
                                    "confidence_grade": row["confidence_grade"],
                                },
                                ensure_ascii=False,
                            ),
                            "entity_ids": json.dumps(
                                [subject_id, object_id],
                                ensure_ascii=False,
                            ),
                        }
                    )

                    if subject_id not in touched_nodes:
                        touched_nodes[subject_id] = GraphNode(
                            id=subject_id,
                            name=subject_name,
                            type=subject_class,
                            domain=domain_for_class(subject_class),
                            summary=f"外部文献标准化实体；原始名称：{row['subject'].strip()}。",
                            aliases=[row["subject"].strip()] if row["subject"].strip() != subject_name else [],
                            is_demo=False,
                        )
                    if object_id not in touched_nodes:
                        touched_nodes[object_id] = GraphNode(
                            id=object_id,
                            name=object_name,
                            type=object_class,
                            domain=domain_for_class(object_class),
                            summary=f"外部文献标准化实体；原始名称：{row['object'].strip()}。",
                            aliases=[row["object"].strip()] if row["object"].strip() != object_name else [],
                            is_demo=False,
                        )
                    touched_edges.append(
                        (
                            row_index,
                            GraphEdge(
                                id=edge_id,
                                source=subject_id,
                                target=object_id,
                                predicate=predicate,
                                evidence_ids=[evidence_id],
                                evidence_level=row["evidence_grade"].strip()
                                or "unclassified",
                                confidence=confidence_value(row["confidence_score"]),
                                is_demo=False,
                            ),
                        )
                    )
                    imported_rows += 1

            self._write_metadata(
                snapshot,
                source_rows.values(),
                document_rows.values(),
                chunk_rows,
                batch_size=batch_size,
            )
            existing_node_ids = {
                node.id for node in snapshot.graph.all_nodes(refresh=True)
            }
            existing_edge_ids = {edge.id for edge in snapshot.graph.all_edges()}
            for node in touched_nodes.values():
                if node.id not in existing_node_ids:
                    snapshot.graph.add_node(node)
            for _, edge in touched_edges:
                if edge.id in existing_edge_ids:
                    continue
                snapshot.graph.add_edge(edge)
            for offset in range(0, len(chunk_rows), 500):
                snapshot.vectors.upsert_many(
                    [
                        (
                            item["chunk_id"],
                            item["text"],
                            {
                                "kind": "external_triple",
                                "is_demo": False,
                                "source_id": item["source_id"],
                            },
                        )
                        for item in chunk_rows[offset : offset + 500]
                    ]
                )

            manifest_path = snapshot.root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            counts = snapshot.metadata.counts()
            graph_counts = snapshot.graph.stats()
            manifest.update(
                {
                    "source_count": counts["sources"],
                    "chunk_count": counts["chunks"],
                    "entity_count": graph_counts["nodes"],
                    "relation_count": graph_counts["edges"],
                    "is_demo": False,
                }
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if activate:
                snapshot.close()
                self.manager.activate(snapshot.version)
            return {
                "snapshot_version": snapshot.version,
                "rows": imported_rows,
                "skipped_rows": skipped_rows,
                "sources": len(source_rows),
                "nodes_added": len(touched_nodes),
                "edges_added": len(touched_edges),
                "warnings": warnings[:100],
            }
        finally:
            snapshot.close()

    @staticmethod
    def _write_metadata(
        snapshot: SnapshotContext,
        sources,
        documents,
        chunks: list[dict[str, str]],
        batch_size: int,
    ) -> None:
        with snapshot.metadata.connect() as connection:
            for source in sources:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO sources (
                        id, title, source_type, source_classification, data_origin,
                        data_owner, access_scope, publisher, published_at, url,
                        is_demo, metadata_json
                    ) VALUES (?, ?, ?, 'external_literature_triple', 'external',
                              ?, 'public', ?, ?, ?, 0, ?)
                    """,
                    (
                        source["source_id"],
                        source["title"],
                        source["source_type"],
                        source["publisher"],
                        source["publisher"],
                        source["published_at"],
                        source["url"],
                        source["metadata_json"],
                    ),
                )
            for document in documents:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO documents
                    (id, source_id, title, content_type, checksum, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, '{}', ?)
                    """,
                    (
                        document["document_id"],
                        document["source_id"],
                        document["title"],
                        document["content_type"],
                        document["checksum"],
                        utc_now(),
                    ),
                )
            for index in range(0, len(chunks), batch_size):
                for chunk in chunks[index : index + batch_size]:
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO chunks (
                            id, document_id, source_id, locator, text,
                            entity_ids_json, metadata_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk["chunk_id"],
                            chunk["document_id"],
                            chunk["source_id"],
                            chunk["locator"],
                            chunk["text"],
                            chunk["entity_ids"],
                            chunk["metadata_json"],
                            utc_now(),
                        ),
                    )
                    connection.execute(
                        "DELETE FROM chunk_fts WHERE chunk_id = ?",
                        (chunk["chunk_id"],),
                    )
                    connection.execute(
                        "INSERT INTO chunk_fts(chunk_id, text_tokens) VALUES (?, ?)",
                        (chunk["chunk_id"], tokenize(chunk["text"])),
                    )
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO evidence (
                            id, chunk_id, source_id, claim, evidence_level,
                            confidence, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk["evidence_id"],
                            chunk["chunk_id"],
                            chunk["source_id"],
                            chunk["claim"],
                            chunk["evidence_level"],
                            chunk["confidence"],
                            chunk["metadata_json"],
                        ),
                    )
