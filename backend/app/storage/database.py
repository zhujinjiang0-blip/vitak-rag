from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jieba


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def tokenize(text: str) -> str:
    tokens = [token.strip().lower() for token in jieba.cut_for_search(text)]
    return " ".join(token for token in tokens if token)


class MetadataStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_classification TEXT NOT NULL DEFAULT '',
                    data_origin TEXT NOT NULL DEFAULT 'external',
                    data_owner TEXT NOT NULL DEFAULT '',
                    access_scope TEXT NOT NULL DEFAULT 'public',
                    publisher TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    is_demo INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id)
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    locator TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL,
                    entity_ids_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(source_id) REFERENCES sources(id)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    edge_id TEXT NOT NULL DEFAULT '',
                    chunk_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    evidence_level TEXT NOT NULL DEFAULT 'demo',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    source_type TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT '',
                    input_status TEXT NOT NULL DEFAULT '',
                    fusion_status TEXT NOT NULL DEFAULT '',
                    evidence_status TEXT NOT NULL DEFAULT '',
                    graph_display_role TEXT NOT NULL DEFAULT '',
                    answer_eligible INTEGER NOT NULL DEFAULT 1,
                    source_record_id TEXT NOT NULL DEFAULT '',
                    source_version TEXT NOT NULL DEFAULT '',
                    source_locator TEXT NOT NULL DEFAULT '',
                    source_file TEXT NOT NULL DEFAULT '',
                    source_row_value TEXT NOT NULL DEFAULT '',
                    test_family TEXT NOT NULL DEFAULT '',
                    analysis_context TEXT NOT NULL DEFAULT '',
                    effect_size TEXT NOT NULL DEFAULT '',
                    ci_low TEXT NOT NULL DEFAULT '',
                    ci_high TEXT NOT NULL DEFAULT '',
                    p_value TEXT NOT NULL DEFAULT '',
                    q_value TEXT NOT NULL DEFAULT '',
                    sample_n TEXT NOT NULL DEFAULT '',
                    model_type TEXT NOT NULL DEFAULT '',
                    core_48_flag INTEGER NOT NULL DEFAULT 0,
                    retention_status TEXT NOT NULL DEFAULT '',
                    conflict_id TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(chunk_id) REFERENCES chunks(id),
                    FOREIGN KEY(source_id) REFERENCES sources(id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                    chunk_id UNINDEXED,
                    text_tokens,
                    tokenize='unicode61'
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS query_logs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    query TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    sufficiency TEXT NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    data_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS unmet_needs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL DEFAULT '',
                    query TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    intent TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    data_scope_json TEXT NOT NULL DEFAULT '[]',
                    data_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending_review',
                    reviewer_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_items (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    candidate_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewer TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    version TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_review_status ON review_items(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_unmet_needs_status
                ON unmet_needs(status, created_at DESC);
                """
            )
            self._migrate_source_columns(connection)
            self._migrate_evidence_columns(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_review ON evidence(review_status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_source_type ON evidence(source_type)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_answer_eligible ON evidence(answer_eligible)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_chunk ON evidence(chunk_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_internal_family "
                "ON evidence(source_type, test_family, core_48_flag)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_result_status "
                "ON evidence(evidence_status, evidence_level)"
            )

    @staticmethod
    def _migrate_source_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sources)").fetchall()
        }
        additions = {
            "source_classification": "TEXT NOT NULL DEFAULT ''",
            "data_origin": "TEXT NOT NULL DEFAULT 'external'",
            "data_owner": "TEXT NOT NULL DEFAULT ''",
            "access_scope": "TEXT NOT NULL DEFAULT 'public'",
        }
        added_any = False
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE sources ADD COLUMN {name} {definition}")
                added_any = True
        if not added_any:
            return
        connection.execute(
            """
            UPDATE sources
            SET source_classification = source_type
            WHERE source_classification = ''
            """
        )
        connection.execute(
            """
            UPDATE sources
            SET data_owner = publisher
            WHERE data_owner = ''
            """
        )
        connection.execute(
            """
            UPDATE sources
            SET data_origin = CASE
                WHEN metadata_json LIKE '%imported_path%' THEN 'internal'
                WHEN is_demo = 1 THEN 'synthetic'
                ELSE 'public'
            END,
            access_scope = CASE
                WHEN metadata_json LIKE '%imported_path%' THEN 'private'
                ELSE 'public'
            END
            WHERE data_origin = 'external'
            """
        )

    @staticmethod
    def _migrate_evidence_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(evidence)").fetchall()
        }
        additions = {
            "edge_id": "TEXT NOT NULL DEFAULT ''",
            "source_type": "TEXT NOT NULL DEFAULT ''",
            "review_status": "TEXT NOT NULL DEFAULT ''",
            "input_status": "TEXT NOT NULL DEFAULT ''",
            "fusion_status": "TEXT NOT NULL DEFAULT ''",
            "evidence_status": "TEXT NOT NULL DEFAULT ''",
            "graph_display_role": "TEXT NOT NULL DEFAULT ''",
            "answer_eligible": "INTEGER NOT NULL DEFAULT 1",
            "source_record_id": "TEXT NOT NULL DEFAULT ''",
            "source_version": "TEXT NOT NULL DEFAULT ''",
            "source_locator": "TEXT NOT NULL DEFAULT ''",
            "source_file": "TEXT NOT NULL DEFAULT ''",
            "source_row_value": "TEXT NOT NULL DEFAULT ''",
            "test_family": "TEXT NOT NULL DEFAULT ''",
            "analysis_context": "TEXT NOT NULL DEFAULT ''",
            "effect_size": "TEXT NOT NULL DEFAULT ''",
            "ci_low": "TEXT NOT NULL DEFAULT ''",
            "ci_high": "TEXT NOT NULL DEFAULT ''",
            "p_value": "TEXT NOT NULL DEFAULT ''",
            "q_value": "TEXT NOT NULL DEFAULT ''",
            "sample_n": "TEXT NOT NULL DEFAULT ''",
            "model_type": "TEXT NOT NULL DEFAULT ''",
            "core_48_flag": "INTEGER NOT NULL DEFAULT 0",
            "retention_status": "TEXT NOT NULL DEFAULT ''",
            "conflict_id": "TEXT NOT NULL DEFAULT ''",
        }
        added_any = False
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE evidence ADD COLUMN {name} {definition}")
                added_any = True
        if added_any:
            connection.execute(
                """
                UPDATE evidence
                SET source_type = 'legacy'
                WHERE source_type = ''
                """
            )
            connection.execute(
                """
                UPDATE evidence
                SET review_status = 'accepted'
                WHERE review_status = ''
                """
            )
        connection.execute(
            """
            UPDATE evidence
            SET
                test_family = COALESCE(NULLIF(test_family, ''),
                    json_extract(metadata_json, '$.test_family'), ''),
                analysis_context = COALESCE(NULLIF(analysis_context, ''),
                    json_extract(metadata_json, '$.analysis_context'), ''),
                effect_size = COALESCE(NULLIF(effect_size, ''),
                    json_extract(metadata_json, '$.effect_size'), ''),
                ci_low = COALESCE(NULLIF(ci_low, ''),
                    json_extract(metadata_json, '$.ci_low'), ''),
                ci_high = COALESCE(NULLIF(ci_high, ''),
                    json_extract(metadata_json, '$.ci_high'), ''),
                p_value = COALESCE(NULLIF(p_value, ''),
                    json_extract(metadata_json, '$.p_value'), ''),
                q_value = COALESCE(NULLIF(q_value, ''),
                    json_extract(metadata_json, '$.q_value'), ''),
                sample_n = COALESCE(NULLIF(sample_n, ''),
                    json_extract(metadata_json, '$.sample_n'), ''),
                model_type = COALESCE(NULLIF(model_type, ''),
                    json_extract(metadata_json, '$.model_type'), ''),
                core_48_flag = CASE
                    WHEN lower(COALESCE(json_extract(metadata_json, '$.core_48_flag'), 'false'))
                         IN ('true', '1') THEN 1
                    ELSE 0
                END,
                retention_status = COALESCE(NULLIF(retention_status, ''),
                    json_extract(metadata_json, '$.retention_status'), ''),
                conflict_id = COALESCE(NULLIF(conflict_id, ''),
                    json_extract(metadata_json, '$.conflict_id'), '')
            WHERE metadata_json != '{}'
            """
        )

    def has_demo_data(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM sources").fetchone()
            return bool(row and row["count"])

    def add_source(
        self,
        source_id: str,
        title: str,
        source_type: str,
        source_classification: str = "",
        data_origin: str = "external",
        data_owner: str = "",
        access_scope: str = "public",
        publisher: str = "",
        published_at: str = "",
        url: str = "",
        is_demo: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sources
                (
                    id, title, source_type, source_classification, data_origin,
                    data_owner, access_scope, publisher, published_at, url,
                    is_demo, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    title,
                    source_type,
                    source_classification or source_type,
                    data_origin,
                    data_owner or publisher,
                    access_scope,
                    publisher,
                    published_at,
                    url,
                    int(is_demo),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    def add_document(
        self,
        document_id: str,
        source_id: str,
        title: str,
        content_type: str,
        checksum: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, source_id, title, content_type, checksum, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    source_id,
                    title,
                    content_type,
                    checksum,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )

    def add_chunk(
        self,
        chunk_id: str,
        document_id: str,
        source_id: str,
        text: str,
        locator: str = "",
        entity_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entity_ids = entity_ids or []
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO chunks
                (id, document_id, source_id, locator, text, entity_ids_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    document_id,
                    source_id,
                    locator,
                    text,
                    json.dumps(entity_ids, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )
            connection.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
            connection.execute(
                "INSERT INTO chunk_fts(chunk_id, text_tokens) VALUES (?, ?)",
                (chunk_id, tokenize(text)),
            )

    def add_evidence(
        self,
        evidence_id: str,
        chunk_id: str,
        source_id: str,
        claim: str,
        evidence_level: str = "demo",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
        edge_id: str = "",
        source_type: str = "",
        review_status: str = "accepted",
        input_status: str = "adopted",
        fusion_status: str = "accepted",
        evidence_status: str = "",
        graph_display_role: str = "",
        answer_eligible: bool = True,
        source_record_id: str = "",
        source_version: str = "",
        source_locator: str = "",
        source_file: str = "",
        source_row_value: str = "",
    ) -> None:
        metadata = metadata or {}
        core_48 = str(metadata.get("core_48_flag", "")).lower() in {"true", "1"}
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence
                (
                    id, edge_id, chunk_id, source_id, claim, evidence_level,
                    confidence, source_type, review_status, input_status,
                    fusion_status, evidence_status, graph_display_role,
                    answer_eligible, source_record_id, source_version,
                    source_locator, source_file, source_row_value,
                    test_family, analysis_context, effect_size, ci_low, ci_high,
                    p_value, q_value, sample_n, model_type, core_48_flag,
                    retention_status, conflict_id, metadata_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    evidence_id,
                    edge_id,
                    chunk_id,
                    source_id,
                    claim,
                    evidence_level,
                    confidence,
                    source_type,
                    review_status,
                    input_status,
                    fusion_status,
                    evidence_status,
                    graph_display_role,
                    int(answer_eligible),
                    source_record_id,
                    source_version,
                    source_locator,
                    source_file,
                    source_row_value,
                    str(metadata.get("test_family", "")),
                    str(metadata.get("analysis_context", "")),
                    str(metadata.get("effect_size", "")),
                    str(metadata.get("ci_low", "")),
                    str(metadata.get("ci_high", "")),
                    str(metadata.get("p_value", "")),
                    str(metadata.get("q_value", "")),
                    str(metadata.get("sample_n", "")),
                    str(metadata.get("model_type", "")),
                    int(core_48),
                    str(metadata.get("retention_status", "")),
                    str(metadata.get("conflict_id", "")),
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT e.*, c.text AS chunk_text, c.locator, c.entity_ids_json,
                       s.title, s.source_type,
                       s.source_classification, s.data_origin, s.data_owner,
                       s.access_scope, s.publisher, s.published_at, s.url, s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                WHERE e.id = ?
                """,
                (evidence_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_evidence_many(self, evidence_ids: list[str]) -> list[dict[str, Any]]:
        if not evidence_ids:
            return []
        placeholders = ",".join("?" for _ in evidence_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.*, c.text AS chunk_text, c.locator, s.title, s.source_type,
                       s.source_classification, s.data_origin, s.data_owner,
                       s.access_scope, s.publisher, s.published_at, s.url, s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                WHERE e.id IN ({placeholders})
                """,
                evidence_ids,
            ).fetchall()
            by_id = {row["id"]: dict(row) for row in rows}
            return [by_id[item] for item in evidence_ids if item in by_id]

    def get_evidence_by_edge_ids(self, edge_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not edge_ids:
            return {}
        placeholders = ",".join("?" for _ in edge_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM evidence
                WHERE edge_id IN ({placeholders})
                ORDER BY id
                """,
                edge_ids,
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result.setdefault(row["edge_id"], dict(row))
        return result

    def all_evidence(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.text AS chunk_text, c.entity_ids_json, c.locator,
                       s.title, s.source_type, s.source_classification,
                       s.data_origin, s.data_owner, s.access_scope,
                       s.publisher, s.published_at, s.url, s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                ORDER BY e.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def all_internal_evidence(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.text AS chunk_text, c.entity_ids_json, c.locator,
                       s.title, s.source_type AS source_table_type,
                       s.source_classification, s.data_origin, s.data_owner,
                       s.access_scope, s.publisher, s.published_at, s.url,
                       s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                WHERE s.data_origin = 'internal'
                ORDER BY e.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def search_fts(
        self,
        query: str,
        limit: int = 10,
        source_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        terms = [term for term in tokenize(query).split() if term]
        if not terms:
            return []
        match_query = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        source_clause = ""
        parameters: list[Any] = [match_query]
        if source_types:
            placeholders = ",".join("?" for _ in source_types)
            source_clause = f"AND e.source_type IN ({placeholders})"
            parameters.extend(sorted(source_types))
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.id, c.document_id, c.source_id, c.text, c.entity_ids_json,
                       c.locator, s.title, s.source_classification,
                       s.data_origin, s.data_owner, s.access_scope, s.is_demo,
                       s.publisher, s.published_at, s.url,
                       e.id AS evidence_id, e.source_type, e.review_status, e.input_status,
                       e.fusion_status, e.evidence_status, e.graph_display_role,
                       e.answer_eligible, e.source_record_id, e.source_version,
                       e.source_locator, e.edge_id,
                       e.metadata_json AS evidence_metadata_json,
                       bm25(chunk_fts) AS rank
                FROM chunk_fts
                JOIN chunks c ON c.id = chunk_fts.chunk_id
                JOIN sources s ON s.id = c.source_id
                LEFT JOIN evidence e ON e.chunk_id = c.id
                WHERE chunk_fts MATCH ?
                {source_clause}
                ORDER BY rank
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def search_evidence_phrases(
        self,
        phrases: list[str],
        *,
        limit: int = 100,
        source_types: set[str] | None = None,
    ) -> list[str]:
        phrases = [phrase for phrase in phrases if phrase.strip()]
        if not phrases:
            return []
        phrase_clause = " OR ".join("c.text LIKE ?" for _ in phrases)
        source_clause = ""
        parameters: list[Any] = [f"%{phrase}%" for phrase in phrases]
        if source_types:
            placeholders = ",".join("?" for _ in source_types)
            source_clause = f"AND e.source_type IN ({placeholders})"
            parameters.extend(sorted(source_types))
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.id
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                WHERE ({phrase_clause})
                  AND e.answer_eligible = 1
                  {source_clause}
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, s.title, s.source_type, s.source_classification,
                       s.data_origin, s.data_owner, s.access_scope,
                       s.publisher, s.published_at, s.url, s.is_demo,
                       e.id AS evidence_id, e.edge_id, e.source_type AS evidence_source_type,
                       e.review_status, e.input_status, e.fusion_status,
                       e.evidence_status, e.graph_display_role, e.answer_eligible,
                       e.source_record_id, e.source_version, e.source_locator,
                       e.metadata_json AS evidence_metadata_json
                FROM chunks c
                JOIN sources s ON s.id = c.source_id
                LEFT JOIN evidence e ON e.chunk_id = c.id
                WHERE c.id = ?
                """,
                (chunk_id,),
            ).fetchone()
            return dict(row) if row else None

    def all_chunks(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, s.title, s.source_type, s.source_classification,
                       s.data_origin, s.data_owner, s.access_scope,
                       s.publisher, s.published_at, s.url, s.is_demo,
                       e.source_type AS evidence_source_type,
                       e.review_status, e.input_status, e.fusion_status,
                       e.evidence_status, e.graph_display_role, e.answer_eligible,
                       e.source_record_id, e.source_version, e.source_locator
                FROM chunks c
                JOIN sources s ON s.id = c.source_id
                LEFT JOIN evidence e ON e.chunk_id = c.id
                ORDER BY c.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        names = ("sources", "documents", "chunks", "evidence")
        with self.connect() as connection:
            return {
                name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                for name in names
            }

    def create_session(self, session_id: str | None = None, ttl_hours: int = 24) -> str:
        session_id = session_id or str(uuid.uuid4())
        now = datetime.now(UTC)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(id, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, expires_at=excluded.expires_at
                """,
                (
                    session_id,
                    now.isoformat(),
                    now.isoformat(),
                    (now + timedelta(hours=ttl_hours)).isoformat(),
                ),
            )
        return session_id

    def session_exists(self, session_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sessions WHERE id = ? AND expires_at > ?",
                (session_id, datetime.now(UTC).isoformat()),
            ).fetchone()
            return bool(row)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(id, session_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )
        return message_id

    def get_recent_messages(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, metadata_json, created_at
                FROM messages WHERE session_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def log_query(
        self,
        session_id: str | None,
        query: str,
        intent: str,
        sufficiency: str,
        elapsed_ms: int,
        data_version: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO query_logs
                (id, session_id, query, intent, sufficiency, elapsed_ms, data_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    session_id,
                    query,
                    intent,
                    sufficiency,
                    elapsed_ms,
                    data_version,
                    utc_now(),
                ),
            )

    def record_unmet_need(
        self,
        *,
        query: str,
        mode: str,
        reason: str,
        data_version: str,
        session_id: str | None = None,
        intent: str = "",
        detail: str = "",
        data_scope: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        record_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO unmet_needs
                (
                    id, session_id, query, mode, intent, reason, detail,
                    data_scope_json, data_version, status, reviewer_note,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', '', ?, ?)
                """,
                (
                    record_id,
                    session_id or "",
                    query.strip(),
                    mode,
                    intent,
                    reason,
                    detail.strip(),
                    json.dumps(data_scope or [], ensure_ascii=False),
                    data_version,
                    now,
                    now,
                ),
            )
        return {
            "id": record_id,
            "session_id": session_id or "",
            "query": query.strip(),
            "mode": mode,
            "intent": intent,
            "reason": reason,
            "detail": detail.strip(),
            "data_scope": data_scope or [],
            "data_version": data_version,
            "status": "pending_review",
            "reviewer_note": "",
            "created_at": now,
            "updated_at": now,
        }

    def list_unmet_needs(
        self,
        *,
        status: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        status_clause = ""
        parameters: list[Any] = []
        if status:
            status_clause = "WHERE status = ?"
            parameters.append(status)
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM unmet_needs
                {status_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["data_scope"] = json.loads(item.pop("data_scope_json") or "[]")
            items.append(item)
        return items

    def add_review_candidates(self, job_id: str, candidates: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for candidate in candidates:
                connection.execute(
                    """
                    INSERT INTO review_items
                    (id, job_id, candidate_type, payload_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        candidate["id"],
                        job_id,
                        candidate["candidate_type"],
                        json.dumps(candidate, ensure_ascii=False),
                        now,
                        now,
                    ),
                )

    def list_review_items(self, status: str = "pending") -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_items WHERE status = ? ORDER BY created_at
                """,
                (status,),
            ).fetchall()
        items = []
        for row in rows:
            record = dict(row)
            record["payload"] = json.loads(record.pop("payload_json"))
            items.append(record)
        return items

    def decide_review(self, candidate_ids: list[str], decision: str, reviewer: str) -> int:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        ids = candidate_ids or [
            item["id"] for item in self.list_review_items("pending")
        ]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE review_items
                SET status = ?, reviewer = ?, updated_at = ?
                WHERE id IN ({placeholders})
                """,
                [decision + "d", reviewer, utc_now(), *ids],
            )
        return len(ids)

    def add_snapshot(self, version: str, path: str, status: str, is_demo: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO snapshots(version, path, status, is_demo, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (version, path, status, int(is_demo), utc_now()),
            )

    def mark_snapshot_active(self, version: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE snapshots SET status = 'ready' WHERE status = 'active'")
            connection.execute(
                "UPDATE snapshots SET status = 'active', activated_at = ? WHERE version = ?",
                (utc_now(), version),
            )
