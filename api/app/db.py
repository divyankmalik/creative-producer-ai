"""Supabase / Postgres client access."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


async def get_pg_pool():
    # TODO: create/return an asyncpg (or psycopg) pool over settings.database_url,
    # used by the LangGraph Postgres checkpointer and any raw SQL (e.g. mark_dependents_stale).
    raise NotImplementedError
