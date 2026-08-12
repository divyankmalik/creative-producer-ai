"""Environment-backed settings for the showrunner API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root (see README setup), not under api/, so anchor to
# this file's location rather than relying on the process's cwd.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str
    database_url: str

    gemini_api_key: str
    groq_api_key: str
    tavily_api_key: str

    max_parallel_nodes: int = 3
    default_node_timeout_s: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
