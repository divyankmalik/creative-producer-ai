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

    # Comma-separated, not a JSON list -- plain text is far easier to paste
    # into a hosting platform's env var UI than JSON-array syntax, which is
    # what pydantic-settings would otherwise require for a real list field.
    # Defaults cover local dev; a real deployment sets this to its actual
    # frontend origin(s) (e.g. "https://showrunner.vercel.app").
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    max_parallel_nodes: int = 3
    default_node_timeout_s: int = 120

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
