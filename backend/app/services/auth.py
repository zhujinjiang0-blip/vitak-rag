from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.schemas import AuthUser, UserRole

ROLE_ADMIN = UserRole.ADMIN


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_password(password: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=32,
    )


def password_digest(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = _hash_password(password, salt, n=n, r=r, p=p)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = _hash_password(
            password,
            bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthStore:
    def __init__(self, path: Path, session_ttl_hours: int = 24):
        self.path = path
        self.session_ttl_hours = session_ttl_hours
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE TABLE IF NOT EXISTS research_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor_id TEXT,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_research_sessions_user
                ON research_sessions(user_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_audit_created
                ON audit_logs(created_at DESC);
                """
            )

    def _audit(
        self,
        connection: sqlite3.Connection,
        action: str,
        *,
        actor_id: str | None = None,
        target: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_logs
            (id, actor_id, action, target, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                actor_id,
                action,
                target,
                json.dumps(metadata or {}, ensure_ascii=False),
                _now().isoformat(),
            ),
        )

    def create_user(
        self,
        username: str,
        password: str,
        *,
        display_name: str = "",
        role: UserRole = UserRole.RESEARCHER,
        expires_at: str | None = None,
        actor_id: str | None = None,
    ) -> AuthUser:
        username = username.strip().lower()
        if not username:
            raise ValueError("username is required")
        if len(password) < 8:
            raise ValueError("password must contain at least 8 characters")
        user_id = str(uuid.uuid4())
        now = _now().isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users
                (id, username, display_name, password_hash, role, active,
                 created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    display_name.strip() or username,
                    password_digest(password),
                    role.value,
                    now,
                    now,
                    expires_at,
                ),
            )
            self._audit(
                connection,
                "user_created",
                actor_id=actor_id,
                target=user_id,
                metadata={"username": username, "role": role.value},
            )
        return AuthUser(
            id=user_id,
            username=username,
            display_name=display_name.strip() or username,
            role=role,
            active=True,
            expires_at=expires_at,
        )

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> tuple[AuthUser, str] | None:
        normalized = username.strip().lower()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (normalized,),
            ).fetchone()
            if (
                not row
                or not bool(row["active"])
                or not password_matches(password, row["password_hash"])
                or self._is_expired(row["expires_at"])
            ):
                self._audit(
                    connection,
                    "login_failed",
                    target=normalized,
                )
                return None
            token = secrets.token_urlsafe(32)
            now = _now()
            session_expires = now + timedelta(hours=self.session_ttl_hours)
            connection.execute(
                """
                INSERT INTO research_sessions
                (token_hash, user_id, created_at, last_seen_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _token_hash(token),
                    row["id"],
                    now.isoformat(),
                    now.isoformat(),
                    session_expires.isoformat(),
                ),
            )
            self._audit(
                connection,
                "login_succeeded",
                actor_id=row["id"],
                target=row["id"],
            )
            user = self._row_to_user(row, session_expires.isoformat())
            return user, token

    def resolve_session(self, token: str | None) -> AuthUser | None:
        if not token:
            return None
        now = _now().isoformat()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT u.*, s.expires_at AS session_expires_at
                FROM research_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                  AND s.revoked_at IS NULL
                  AND s.expires_at > ?
                  AND u.active = 1
                  AND (u.expires_at IS NULL OR u.expires_at > ?)
                """,
                (_token_hash(token), now, now),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """
                UPDATE research_sessions SET last_seen_at = ?
                WHERE token_hash = ?
                """,
                (now, _token_hash(token)),
            )
            return self._row_to_user(row, row["session_expires_at"])

    def logout(self, token: str | None, actor_id: str | None = None) -> None:
        if not token:
            return
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE research_sessions SET revoked_at = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (_now().isoformat(), _token_hash(token)),
            )
            self._audit(connection, "logout", actor_id=actor_id)

    def set_active(
        self,
        user_id_or_name: str,
        active: bool,
        *,
        actor_id: str | None = None,
    ) -> bool:
        with self.connect() as connection:
            row = self._find_user(connection, user_id_or_name)
            if not row:
                return False
            connection.execute(
                "UPDATE users SET active = ?, updated_at = ? WHERE id = ?",
                (int(active), _now().isoformat(), row["id"]),
            )
            if not active:
                connection.execute(
                    """
                    UPDATE research_sessions SET revoked_at = ?
                    WHERE user_id = ? AND revoked_at IS NULL
                    """,
                    (_now().isoformat(), row["id"]),
                )
            self._audit(
                connection,
                "user_status_changed",
                actor_id=actor_id,
                target=row["id"],
                metadata={"active": active},
            )
            return True

    def reset_password(
        self,
        user_id_or_name: str,
        password: str,
        *,
        actor_id: str | None = None,
    ) -> bool:
        if len(password) < 8:
            raise ValueError("password must contain at least 8 characters")
        with self.connect() as connection:
            row = self._find_user(connection, user_id_or_name)
            if not row:
                return False
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (password_digest(password), _now().isoformat(), row["id"]),
            )
            connection.execute(
                """
                UPDATE research_sessions SET revoked_at = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (_now().isoformat(), row["id"]),
            )
            self._audit(
                connection,
                "password_reset",
                actor_id=actor_id,
                target=row["id"],
            )
            return True

    def revoke_sessions(
        self,
        user_id_or_name: str,
        *,
        actor_id: str | None = None,
    ) -> int:
        with self.connect() as connection:
            row = self._find_user(connection, user_id_or_name)
            if not row:
                return 0
            cursor = connection.execute(
                """
                UPDATE research_sessions SET revoked_at = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (_now().isoformat(), row["id"]),
            )
            self._audit(
                connection,
                "sessions_revoked",
                actor_id=actor_id,
                target=row["id"],
                metadata={"count": cursor.rowcount},
            )
            return int(cursor.rowcount)

    def list_users(self) -> list[AuthUser]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY created_at"
            ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            output.append(item)
        return output

    def audit_access(
        self,
        actor_id: str | None,
        action: str,
        *,
        target: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            self._audit(
                connection,
                action,
                actor_id=actor_id,
                target=target,
                metadata=metadata,
            )

    @staticmethod
    def _find_user(
        connection: sqlite3.Connection,
        user_id_or_name: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM users WHERE id = ? OR username = ?",
            (user_id_or_name, user_id_or_name.strip().lower()),
        ).fetchone()

    @staticmethod
    def _is_expired(value: str | None) -> bool:
        return bool(value and value <= _now().isoformat())

    @staticmethod
    def _row_to_user(
        row: sqlite3.Row,
        session_expires_at: str | None = None,
    ) -> AuthUser:
        return AuthUser(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            role=UserRole(row["role"]),
            active=bool(row["active"]),
            expires_at=row["expires_at"],
            session_expires_at=session_expires_at,
        )
