"""Wraps the `mark_dependents_stale` Postgres function for edit-driven invalidation."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.db import get_supabase


async def mark_dependents_stale(artifact_id: UUID, reason: str) -> list[str]:
    """Calls mark_dependents_stale() (001_init.sql), which walks HARD
    artifact_dependencies edges transitively (depth-limited to 10) and
    returns the slugs of every artifact it just marked stale directly --
    used as PATCH /artifacts/{id}'s `staleDependents` response field.
    """

    def _call():
        return (
            get_supabase()
            .rpc("mark_dependents_stale", {"p_artifact_id": str(artifact_id), "p_reason": reason})
            .execute()
        )

    response = await asyncio.to_thread(_call)
    return [row["slug"] for row in response.data]
