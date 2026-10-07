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
                    chunk_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    evidence_level TEXT NOT NULL DEFAULT 'demo',
                    confidence REAL NOT NULL DEFAULT 0.5,
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
                (id, title, source_type, publisher, published_at, url, is_demo, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    title,
                    source_type,
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
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence
                (id, chunk_id, source_id, claim, evidence_level, confidence, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    chunk_id,
                    source_id,
                    claim,
                    evidence_level,
                    confidence,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT e.*, c.text AS chunk_text, c.locator, s.title, s.source_type,
                       s.publisher, s.published_at, s.url, s.is_demo
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
                       s.publisher, s.published_at, s.url, s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                WHERE e.id IN ({placeholders})
                """,
                evidence_ids,
            ).fetchall()
            by_id = {row["id"]: dict(row) for row in rows}
            return [by_id[item] for item in evidence_ids if item in by_id]

    def all_evidence(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.text AS chunk_text, c.entity_ids_json, c.locator,
                       s.title, s.source_type, s.publisher, s.published_at,
                       s.url, s.is_demo
                FROM evidence e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN sources s ON s.id = e.source_id
                ORDER BY e.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def search_fts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term for term in tokenize(query).split() if term]
        if not terms:
            return []
        match_query = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.document_id, c.source_id, c.text, c.entity_ids_json,
                       c.locator, s.title, s.is_demo,
                       bm25(chunk_fts) AS rank
                FROM chunk_fts
                JOIN chunks c ON c.id = chunk_fts.chunk_id
                JOIN sources s ON s.id = c.source_id
                WHERE chunk_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, s.title, s.source_type, s.publisher, s.published_at, s.url, s.is_demo
                FROM chunks c JOIN sources s ON s.id = c.source_id
                WHERE c.id = ?
                """,
                (chunk_id,),
            ).fetchone()
            return dict(row) if row else None

    def all_chunks(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, s.title, s.source_type, s.publisher, s.published_at, s.url, s.is_demo
                FROM chunks c JOIN sources s ON s.id = c.source_id
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
