from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

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
    internal_token: str = "change-me-in-local-development"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    session_ttl_hours: int = 24
    max_graph_hops: int = 2

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
