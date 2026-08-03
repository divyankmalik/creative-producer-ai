"""Wraps the `mark_dependents_stale` Postgres function for edit-driven invalidation."""

from __future__ import annotations

from uuid import UUID


async def mark_dependents_stale(artifact_id: UUID, reason: str) -> list[str]:
    # TODO: call `select mark_dependents_stale($1, $2)`, then select the
    # newly-stale artifact slugs to return to the caller (used as PATCH
    # /artifacts/{id}'s `staleDependents` response field).
    raise NotImplementedError
