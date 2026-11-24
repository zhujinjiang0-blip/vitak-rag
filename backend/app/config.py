from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="VITAK_",
        extra="ignore",
    )

    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = PROJECT_ROOT / "data"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    runtime_llm_enabled: bool = False
    runtime_llm_base_url: str = "https://api.deepseek.com/v1"
    runtime_llm_api_key: str = ""
    runtime_llm_model: str = "deepseek-chat"
    runtime_llm_timeout_seconds: float = 30.0
    runtime_llm_temperature: float = 0.2
    runtime_llm_max_context_chars: int = 18000
    runtime_llm_json_mode: bool = True
    runtime_llm_endpoint_class: Literal[
        "cloud_public",
        "private_network",
    ] = "cloud_public"
    runtime_llm_allow_protected_evidence: bool = False
    session_ttl_hours: int = 24
    max_graph_hops: int = 2
    research_snapshot_version: str = "vitak-research-2026.11-t02"
    auth_db_path: Path | None = None
    session_cookie_name: str = "vitak_research_session"

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        return path

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def runtime_dir(self) -> Path:
        return self.data_dir / "runtime"

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def active_manifest(self) -> Path:
        return self.runtime_dir / "active_snapshot.json"

    @property
    def review_dir(self) -> Path:
        return self.data_dir / "review"

    @property
    def resolved_auth_db_path(self) -> Path:
        if self.auth_db_path:
            path = Path(self.auth_db_path)
            return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
        return self.runtime_dir / "research_auth.sqlite3"

    @property
    def runtime_llm_configured(self) -> bool:
        return bool(
            self.runtime_llm_enabled
            and self.runtime_llm_api_key.strip()
            and self.runtime_llm_base_url.strip()
            and self.runtime_llm_model.strip()
        )

    @property
    def runtime_llm_provider(self) -> str:
        lowered = self.runtime_llm_base_url.lower()
        if "deepseek" in lowered:
            return "deepseek"
        return "openai-compatible"

    @property
    def runtime_llm_private_endpoint(self) -> bool:
        hostname = urlsplit(self.runtime_llm_base_url).hostname
        if not hostname:
            return False
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            return True
        if hostname.endswith((".local", ".internal")):
            return True
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return address.is_private or address.is_loopback

    @property
    def runtime_llm_protected_evidence_allowed(self) -> bool:
        return bool(
            self.runtime_llm_allow_protected_evidence
            and self.runtime_llm_endpoint_class == "private_network"
            and self.runtime_llm_private_endpoint
        )

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.runtime_dir,
            self.snapshots_dir,
            self.review_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
