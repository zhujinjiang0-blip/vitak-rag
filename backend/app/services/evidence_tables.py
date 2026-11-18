from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.external_triples import confidence_value, domain_for_class, stable_id
from app.services.snapshot import SnapshotContext, SnapshotManager
from app.storage.database import tokenize, utc_now

EXPECTED_FIELDS = [
    "edge_id",
    "subject_id",
    "subject_label",
    "subject_type",
    "predicate",
    "object_id",
    "object_label",
    "object_type",
    "source_type",
    "source_record_id",
    "source_locator",
    "source_version",
    "source_sha256",
    "evidence_score",
    "evidence_grade",
    "confidence_score",
    "effect_size",
    "ci_low",
    "ci_high",
    "p_value",
    "q_value",
    "sample_n",
    "model_type",
    "population_context",
    "dose_context",
    "time_context",
    "qualifiers_json",
    "fusion_status",
    "retention_status",
    "conflict_id",
    "review_status",
    "review_reason",
    "input_status",
    "modification_codes",
    "merged_into",
    "test_family",
    "analysis_context",
    "evidence_status",
    "core_48_flag",
    "graph_display_role",
    "source_file",
    "source_row_value",
]
REQUIRED_VALUE_FIELDS = {
    "edge_id",
    "subject_label",
    "subject_type",
    "predicate",
    "object_label",
    "object_type",
    "source_type",
}
SUPPORTED_SOURCE_TYPES = {"internal", "literature", "structured"}
SKIP_EDGE_STATUSES = {"merged_duplicate"}


@dataclass
class EvidenceTablePolicy:
    data_origin: str
    access_scope: str
    source_classification: str
    data_owner: str


SOURCE_POLICIES = {
    "internal": EvidenceTablePolicy(
        data_origin="internal",
        access_scope="private",
        source_classification="internal_rct_evidence",
        data_owner="毕业设计内部资料",
    ),
    "literature": EvidenceTablePolicy(
        data_origin="external",
        access_scope="public",
        source_classification="external_literature_triple",
        data_owner="已发表维生素 K 研究文献",
    ),
    "structured": EvidenceTablePolicy(
        data_origin="external",
        access_scope="public",
        source_classification="external_structured_triple",
        data_owner="FDC、USDA、PubChem、FooDB、KEGG、ClinicalTrials 等外部结构化数据",
    ),
}


@dataclass
class ImportStats:
    files: list[str] = field(default_factory=list)
    rows: int = 0
    graph_edges: int = 0
    skipped_graph_edges: int = 0
    nodes: int = 0
    literal_nodes: int = 0
    sources: int = 0
    documents: int = 0
    chunks: int = 0
    vectors: int = 0
    missing_required: int = 0
    duplicate_edge_ids: int = 0
    node_conflicts: int = 0
    source_types: dict[str, int] = field(default_factory=dict)
    origins: dict[str, int] = field(default_factory=dict)
    review_statuses: dict[str, int] = field(default_factory=dict)
    input_statuses: dict[str, int] = field(default_factory=dict)
    fusion_statuses: dict[str, int] = field(default_factory=dict)
    evidence_statuses: dict[str, int] = field(default_factory=dict)
    answer_eligible: int = 0
    answer_ineligible: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "rows": self.rows,
            "graph_edges": self.graph_edges,
            "skipped_graph_edges": self.skipped_graph_edges,
            "nodes": self.nodes,
            "literal_nodes": self.literal_nodes,
            "sources": self.sources,
            "documents": self.documents,
            "chunks": self.chunks,
            "vectors": self.vectors,
            "missing_required": self.missing_required,
            "duplicate_edge_ids": self.duplicate_edge_ids,
            "node_conflicts": self.node_conflicts,
            "source_types": self.source_types,
            "origins": self.origins,
            "review_statuses": self.review_statuses,
            "input_statuses": self.input_statuses,
            "fusion_statuses": self.fusion_statuses,
            "evidence_statuses": self.evidence_statuses,
            "answer_eligible": self.answer_eligible,
            "answer_ineligible": self.answer_ineligible,
            "warnings": self.warnings[:200],
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def answer_eligible(row: dict[str, str]) -> bool:
    review = (row.get("review_status") or "").strip()
    input_status = (row.get("input_status") or "").strip()
    if review in SKIP_EDGE_STATUSES:
        return False
    return review in {
        "accepted",
        "adopted_with_warning",
        "accepted_internal_ledger",
        "conflict_retained_internal",
    } and input_status == "adopted"


def compact_text(value: str, limit: int = 500) -> str:
    cleaned = (
        re.sub(r"\s+", " ", value or "")
        .strip()
        .replace('"', "'")
        .replace("|", "/")
    )
    return cleaned[:limit]


class EvidenceTableImporter:
    def __init__(self, manager: SnapshotManager):
        self.manager = manager

    def audit(self, paths: Iterable[Path]) -> dict[str, Any]:
        paths = [path.resolve() for path in paths]
        stats = ImportStats(files=[str(path) for path in paths])
        seen_edges: set[str] = set()
        node_labels: dict[str, tuple[str, str]] = {}
        node_conflicts: set[str] = set()
        source_keys: set[str] = set()
        literal_ids: set[str] = set()
        stats.source_types = {}
        source_counter = Counter()
        origin_counter = Counter()
        review_counter = Counter()
        input_counter = Counter()
        fusion_counter = Counter()
        evidence_counter = Counter()
        for path in paths:
            self._validate_header(path)
            with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
                reader = csv.DictReader(handle)
                for row_number, row in enumerate(reader, start=2):
                    stats.rows += 1
                    if not self._row_valid(row):
                        stats.missing_required += 1
                        stats.warnings.append(f"{path.name}:{row_number} 缺少必填字段")
                        continue
                    source_type = row["source_type"].strip()
                    policy = SOURCE_POLICIES.get(source_type)
                    if not policy:
                        stats.warnings.append(
                            f"{path.name}:{row_number} 未知 source_type={source_type}"
                        )
                        continue
                    edge_id = row["edge_id"].strip()
                    if edge_id in seen_edges:
                        stats.duplicate_edge_ids += 1
                        continue
                    seen_edges.add(edge_id)
                    source_counter[source_type] += 1
                    source_keys.add(
                        row["source_record_id"].strip()
                        if source_type == "literature"
                        else row["source_version"].strip()
                    )
                    origin_counter[policy.data_origin] += 1
                    review_counter[row["review_status"].strip()] += 1
                    input_counter[row["input_status"].strip()] += 1
                    fusion_counter[row["fusion_status"].strip()] += 1
                    evidence_counter[row["evidence_status"].strip()] += 1
                    if row["review_status"].strip() in SKIP_EDGE_STATUSES:
                        stats.skipped_graph_edges += 1
                    else:
                        stats.graph_edges += 1
                    if answer_eligible(row):
                        stats.answer_eligible += 1
                    else:
                        stats.answer_ineligible += 1
                    subject_id = row["subject_id"].strip()
                    self._record_node(
                        node_labels,
                        subject_id,
                        row["subject_label"],
                        row["subject_type"],
                        node_conflicts,
                    )
                    object_id = row["object_id"].strip()
                    if not object_id:
                        object_id = stable_id(
                            "literal",
                            row["object_type"].strip(),
                            row["object_label"].strip(),
                        )
                        literal_ids.add(object_id)
                    self._record_node(
                        node_labels,
                        object_id,
                        row["object_label"],
                        row["object_type"],
                        node_conflicts,
                    )
        stats.nodes = len(node_labels)
        stats.sources = len(source_keys)
        stats.documents = len(source_keys)
        stats.node_conflicts = len(node_conflicts)
        stats.literal_nodes = len(literal_ids)
        stats.source_types = dict(source_counter)
        stats.origins = dict(origin_counter)
        stats.review_statuses = dict(review_counter)
        stats.input_statuses = dict(input_counter)
        stats.fusion_statuses = dict(fusion_counter)
        stats.evidence_statuses = dict(evidence_counter)
        return stats.to_dict()

    def import_files(
        self,
        paths: Iterable[Path],
        *,
        version: str,
        activate: bool = False,
        max_rows_per_file: int | None = None,
        build_vectors: bool = True,
        report_path: Path | None = None,
    ) -> dict[str, Any]:
        paths = [path.resolve() for path in paths]
        for path in paths:
            self._validate_header(path)
        snapshot = self.manager.create_empty_snapshot(version)
        stats = ImportStats(files=[str(path) for path in paths])
        seen_edges: set[str] = set()
        source_types = Counter()
        origins = Counter()
        review_statuses = Counter()
        input_statuses = Counter()
        fusion_statuses = Counter()
        evidence_statuses = Counter()
        source_records: dict[str, dict[str, Any]] = {}
        documents: dict[str, dict[str, Any]] = {}
        node_labels: dict[str, tuple[str, str]] = {}
        node_conflicts: set[str] = set()
        literal_ids: set[str] = set()
        temp_root = Path(tempfile.mkdtemp(prefix="vitak-real-import-"))
        nodes_path = temp_root / "nodes.csv"
        edges_path = temp_root / "edges.csv"
        vectors_path = temp_root / "vectors.jsonl"
        try:
            with (
                nodes_path.open("w", encoding="utf-8", newline="") as nodes_file,
                edges_path.open("w", encoding="utf-8", newline="") as edges_file,
                vectors_path.open("w", encoding="utf-8") as vectors_file,
                snapshot.metadata.connect() as connection,
            ):
                node_writer = csv.writer(nodes_file, delimiter="|")
                edge_writer = csv.writer(edges_file, delimiter="|")
                node_writer.writerow(
                    ["id", "name", "type", "domain", "summary", "aliases", "is_demo"]
                )
                edge_writer.writerow(
                    [
                        "from",
                        "to",
                        "id",
                        "predicate",
                        "evidence_ids",
                        "evidence_level",
                        "confidence",
                        "is_demo",
                    ]
                )
                for path in paths:
                    file_hash = file_sha256(path)
                    with path.open(
                        encoding="utf-8-sig",
                        newline="",
                        errors="replace",
                    ) as handle:
                        reader = csv.DictReader(handle)
                        for row_number, row in enumerate(reader, start=2):
                            if max_rows_per_file and row_number - 1 > max_rows_per_file:
                                break
                            stats.rows += 1
                            if not self._row_valid(row):
                                stats.missing_required += 1
                                continue
                            source_type = row["source_type"].strip()
                            policy = SOURCE_POLICIES.get(source_type)
                            if not policy:
                                stats.warnings.append(
                                    f"{path.name}:{row_number} 未知 source_type={source_type}"
                                )
                                continue
                            edge_id = row["edge_id"].strip()
                            if edge_id in seen_edges:
                                stats.duplicate_edge_ids += 1
                                continue
                            seen_edges.add(edge_id)
                            source_type_counter = source_type
                            source_types[source_type_counter] += 1
                            origins[policy.data_origin] += 1
                            review_statuses[row["review_status"].strip()] += 1
                            input_statuses[row["input_status"].strip()] += 1
                            fusion_statuses[row["fusion_status"].strip()] += 1
                            evidence_statuses[row["evidence_status"].strip()] += 1
                            eligible = answer_eligible(row)
                            if eligible:
                                stats.answer_eligible += 1
                            else:
                                stats.answer_ineligible += 1
                            source_id = self._source_id(source_type, row, file_hash)
                            document_id = self._document_id(source_type, row, source_id)
                            source_record = self._source_record(
                                source_id,
                                document_id,
                                source_type,
                                row,
                                policy,
                                path,
                                file_hash,
                            )
                            if source_id not in source_records:
                                source_records[source_id] = source_record
                                self._insert_source(connection, source_record)
                                stats.sources += 1
                            if document_id not in documents:
                                document = {
                                    "id": document_id,
                                    "source_id": source_id,
                                    "title": source_record["title"],
                                    "content_type": "text/csv",
                                    "checksum": file_hash,
                                    "metadata_json": json.dumps(
                                        {
                                            "source_record_id": row["source_record_id"],
                                            "source_version": row["source_version"],
                                        },
                                        ensure_ascii=False,
                                    ),
                                }
                                documents[document_id] = document
                                self._insert_document(connection, document)
                                stats.documents += 1
                            subject_id = row["subject_id"].strip()
                            self._write_node(
                                node_writer,
                                node_labels,
                                node_conflicts,
                                subject_id,
                                row["subject_label"],
                                row["subject_type"],
                                stats,
                            )
                            object_id = row["object_id"].strip()
                            is_literal = not object_id
                            if is_literal:
                                object_id = stable_id(
                                    "literal",
                                    row["object_type"].strip(),
                                    row["object_label"].strip(),
                                )
                                literal_ids.add(object_id)
                            self._write_node(
                                node_writer,
                                node_labels,
                                node_conflicts,
                                object_id,
                                row["object_label"],
                                row["object_type"],
                                stats,
                            )
                            chunk_id = stable_id("CHUNK", edge_id)
                            evidence_id = stable_id("EVID", edge_id)
                            source_text = compact_text(
                                row["source_locator"]
                                or (
                                    f"{row['subject_label']} {row['predicate']} "
                                    f"{row['object_label']}"
                                ),
                                3000,
                            )
                            chunk_text = (
                                f"{row['subject_label']} {row['predicate']} "
                                f"{row['object_label']}。来源定位：{source_text}"
                            )
                            metadata = dict(row)
                            metadata["answer_eligible"] = eligible
                            metadata["literal_object"] = is_literal
                            metadata["input_file_sha256"] = file_hash
                            self._insert_chunk(
                                connection,
                                chunk_id,
                                document_id,
                                source_id,
                                row["source_locator"],
                                chunk_text,
                                [subject_id, object_id],
                                metadata,
                            )
                            self._insert_evidence(
                                connection,
                                evidence_id,
                                edge_id,
                                chunk_id,
                                source_id,
                                chunk_text,
                                row,
                                eligible,
                                metadata,
                            )
                            stats.chunks += 1
                            if (
                                row["review_status"].strip() not in SKIP_EDGE_STATUSES
                            ):
                                edge_writer.writerow(
                                    [
                                        subject_id,
                                        object_id,
                                        compact_text(edge_id, 500),
                                        compact_text(row["predicate"], 500),
                                        json.dumps([evidence_id], ensure_ascii=False),
                                        compact_text(row["evidence_grade"], 100)
                                        or "not_scored",
                                        confidence_value(row["confidence_score"]),
                                        "false",
                                    ]
                                )
                                stats.graph_edges += 1
                            else:
                                stats.skipped_graph_edges += 1
                            if build_vectors:
                                vectors_file.write(
                                    json.dumps(
                                        [
                                            chunk_id,
                                            chunk_text,
                                            {
                                                "source_id": source_id,
                                                "source_type": source_type,
                                                "data_origin": policy.data_origin,
                                                "review_status": row["review_status"],
                                                "input_status": row["input_status"],
                                                "answer_eligible": eligible,
                                                "is_demo": False,
                                            },
                                        ],
                                        ensure_ascii=False,
                                    )
                                    + "\n"
                                )
            snapshot.graph.connection.execute(
                f"COPY Entity FROM '{self._sql_path(nodes_path)}' "
                "(HEADER=true, DELIM='|')"
            )
            snapshot.graph.connection.execute(
                f"COPY RELATES FROM '{self._sql_path(edges_path)}' "
                "(HEADER=true, DELIM='|')"
            )
            if build_vectors:
                vector_batch: list[tuple[str, str, dict[str, Any]]] = []
                with vectors_path.open(encoding="utf-8") as vectors_file:
                    for line in vectors_file:
                        if not line.strip():
                            continue
                        chunk_id, text, metadata = json.loads(line)
                        vector_batch.append((chunk_id, text, metadata))
                        if len(vector_batch) >= 500:
                            snapshot.vectors.upsert_many(vector_batch)
                            stats.vectors += len(vector_batch)
                            vector_batch.clear()
                if vector_batch:
                    snapshot.vectors.upsert_many(vector_batch)
                    stats.vectors += len(vector_batch)
            snapshot.graph._node_cache = None
            stats.nodes = len(node_labels)
            stats.literal_nodes = len(literal_ids)
            stats.node_conflicts = len(node_conflicts)
            stats.source_types = dict(source_types)
            stats.origins = dict(origins)
            stats.review_statuses = dict(review_statuses)
            stats.input_statuses = dict(input_statuses)
            stats.fusion_statuses = dict(fusion_statuses)
            stats.evidence_statuses = dict(evidence_statuses)
            self._update_manifest(snapshot, stats)
            report = stats.to_dict()
            report["version"] = version
            if report_path:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            if activate:
                snapshot.close()
                self.manager.activate(version)
            return report
        except Exception:
            stats.warnings.append("导入失败，快照处于 staged 状态")
            raise
        finally:
            snapshot.close()
            shutil.rmtree(temp_root, ignore_errors=True)

    @staticmethod
    def _validate_header(path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"evidence table not found: {path}")
        with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
            header = next(csv.reader(handle), [])
        missing = [field for field in EXPECTED_FIELDS if field not in header]
        if missing:
            raise ValueError(f"{path.name} 缺少字段: {', '.join(missing)}")

    @staticmethod
    def _row_valid(row: dict[str, str]) -> bool:
        return all((row.get(field) or "").strip() for field in REQUIRED_VALUE_FIELDS)

    @staticmethod
    def _source_id(source_type: str, row: dict[str, str], file_hash: str) -> str:
        if source_type == "literature":
            return stable_id("LIT-SRC", row["source_record_id"])
        return stable_id(
            "INT-SRC" if source_type == "internal" else "STRUCT-SRC",
            row["source_version"] or file_hash,
        )

    @staticmethod
    def _document_id(source_type: str, row: dict[str, str], source_id: str) -> str:
        if source_type == "literature":
            return stable_id("LIT-DOC", row["source_record_id"])
        return f"DOC-{source_id}"

    @staticmethod
    def _source_record(
        source_id: str,
        document_id: str,
        source_type: str,
        row: dict[str, str],
        policy: EvidenceTablePolicy,
        path: Path,
        file_hash: str,
    ) -> dict[str, Any]:
        title = (
            f"文献 {row['source_record_id']}"
            if source_type == "literature"
            else path.stem
        )
        record_id = row["source_record_id"]
        pmid_match = re.search(r"(\d{6,})", record_id)
        url = (
            f"https://pubmed.ncbi.nlm.nih.gov/{pmid_match.group(1)}/"
            if source_type == "literature" and pmid_match
            else ""
        )
        return {
            "id": source_id,
            "title": compact_text(title, 250),
            "source_type": source_type,
            "source_classification": policy.source_classification,
            "data_origin": policy.data_origin,
            "data_owner": policy.data_owner,
            "access_scope": policy.access_scope,
            "publisher": policy.data_owner,
            "published_at": "",
            "url": url,
            "metadata_json": json.dumps(
                {
                    "source_record_id": record_id,
                    "source_version": row["source_version"],
                    "source_sha256": row["source_sha256"],
                    "input_file": str(path),
                    "input_sha256": file_hash,
                },
                ensure_ascii=False,
            ),
            "document_id": document_id,
        }

    @staticmethod
    def _insert_source(connection, source: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO sources (
                id, title, source_type, source_classification, data_origin,
                data_owner, access_scope, publisher, published_at, url,
                is_demo, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                source["id"],
                source["title"],
                source["source_type"],
                source["source_classification"],
                source["data_origin"],
                source["data_owner"],
                source["access_scope"],
                source["publisher"],
                source["published_at"],
                source["url"],
                source["metadata_json"],
            ),
        )

    @staticmethod
    def _insert_document(connection, document: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO documents
            (id, source_id, title, content_type, checksum, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["id"],
                document["source_id"],
                document["title"],
                document["content_type"],
                document["checksum"],
                document["metadata_json"],
                utc_now(),
            ),
        )

    @staticmethod
    def _write_node(
        writer,
        nodes: dict[str, tuple[str, str]],
        conflicts: set[str],
        node_id: str,
        label: str,
        node_type: str,
        stats: ImportStats,
    ) -> None:
        if not node_id:
            node_id = stable_id("entity", node_type, label)
        if node_id in nodes:
            existing = nodes[node_id]
            if existing != (label, node_type):
                conflicts.add(node_id)
            return
        nodes[node_id] = (label, node_type)
        safe_label = compact_text(label, 500)
        safe_type = compact_text(node_type, 160)
        safe_domain = compact_text(domain_for_class(node_type), 80)
        writer.writerow(
            [
                node_id,
                safe_label,
                safe_type,
                safe_domain,
                compact_text(
                    f"真实数据实体：{label}；本体类型：{node_type}。",
                    1000,
                ),
                "[]",
                "false",
            ]
        )

    @classmethod
    def _record_node(
        cls,
        nodes: dict[str, tuple[str, str]],
        node_id: str,
        label: str,
        node_type: str,
        conflicts: set[str],
    ) -> None:
        if node_id in nodes and nodes[node_id] != (label, node_type):
            conflicts.add(node_id)
        else:
            nodes[node_id] = (label, node_type)

    @staticmethod
    def _insert_chunk(
        connection,
        chunk_id: str,
        document_id: str,
        source_id: str,
        locator: str,
        text: str,
        entity_ids: list[str],
        metadata: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO chunks (
                id, document_id, source_id, locator, text, entity_ids_json,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                document_id,
                source_id,
                locator,
                text,
                json.dumps(entity_ids, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                utc_now(),
            ),
        )
        connection.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
        connection.execute(
            "INSERT INTO chunk_fts(chunk_id, text_tokens) VALUES (?, ?)",
            (chunk_id, tokenize(text)),
        )

    @staticmethod
    def _insert_evidence(
        connection,
        evidence_id: str,
        edge_id: str,
        chunk_id: str,
        source_id: str,
        claim: str,
        row: dict[str, str],
        eligible: bool,
        metadata: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO evidence (
                id, edge_id, chunk_id, source_id, claim, evidence_level,
                confidence, source_type, review_status, input_status,
                fusion_status, evidence_status, graph_display_role,
                answer_eligible, source_record_id, source_version,
                source_locator, source_file, source_row_value, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                edge_id,
                chunk_id,
                source_id,
                claim,
                row["evidence_grade"].strip() or "not_scored",
                confidence_value(row["confidence_score"]),
                row["source_type"].strip(),
                row["review_status"].strip(),
                row["input_status"].strip(),
                row["fusion_status"].strip(),
                row["evidence_status"].strip(),
                row["graph_display_role"].strip(),
                int(eligible),
                row["source_record_id"],
                row["source_version"],
                row["source_locator"],
                row["source_file"],
                row["source_row_value"],
                json.dumps(metadata, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _update_manifest(snapshot: SnapshotContext, stats: ImportStats) -> None:
        manifest_path = snapshot.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        counts = snapshot.metadata.counts()
        graph_counts = snapshot.graph.stats()
        manifest.update(
            {
                "is_demo": False,
                "source_count": counts["sources"],
                "chunk_count": counts["chunks"],
                "entity_count": graph_counts["nodes"],
                "relation_count": graph_counts["edges"],
                "import_stats": stats.to_dict(),
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _sql_path(path: Path) -> str:
        return str(path).replace("'", "''")
