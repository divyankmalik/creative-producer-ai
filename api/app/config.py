"""Environment-backed settings for the showrunner API."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    database_url: str

    gemini_api_key: str
    groq_api_key: str
    tavily_api_key: str

    max_parallel_nodes: int = 3
    default_node_timeout_s: int = 120


@lru_cache
def get_settings() -> Settings:
    # TODO: load and cache Settings() from environment / .env
    raise NotImplementedError
