"""CRUD/query helpers over the artifacts and artifact_versions tables."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.db import get_supabase
from app.models import Artifact, Dependency

# Cross-layer import (services/ -> director/) is deliberate here: slug
# naming is a single convention every agent and the Director already share,
# and duplicating the ".replace(...)" logic here risks a second copy
# silently drifting out of sync -- exactly the kind of bug slug_for_node_key
# itself was written to catch (see test_template.py's regression test for
# design.visual_language). template.py has no imports of its own, so this
# doesn't create an actual circular import, just crosses a layer boundary
# for one pure, dependency-free naming function.
from app.director.template import slug_for_node_key


async def get_artifact(artifact_id: UUID) -> Artifact:
    def _fetch():
        return get_supabase().table("artifacts").select("*").eq("id", str(artifact_id)).single().execute()

    response = await asyncio.to_thread(_fetch)
    return Artifact.model_validate(response.data)


async def get_artifact_by_slug(project_id: UUID, slug: str) -> Artifact:
    def _fetch():
        return (
            get_supabase()
            .table("artifacts")
            .select("*")
            .eq("project_id", str(project_id))
            .eq("slug", slug)
            .single()
            .execute()
        )

    response = await asyncio.to_thread(_fetch)
    return Artifact.model_validate(response.data)


async def list_artifacts_for_project(project_id: UUID) -> list[Artifact]:
    """Every artifact a project has produced so far -- used by
    services/export.py to assemble the full bundle, and by GET /projects/{id}
    to build the artifact-summary list the poll loop reads.
    """

    def _fetch():
        return get_supabase().table("artifacts").select("*").eq("project_id", str(project_id)).execute()

    response = await asyncio.to_thread(_fetch)
    return [Artifact.model_validate(row) for row in response.data]


async def try_get_artifact_by_slug(project_id: UUID, slug: str) -> Artifact | None:
    """Like get_artifact_by_slug, but returns None instead of raising when no
    row matches -- for SOFT dependencies, where "doesn't exist yet" is a
    normal outcome, not an error (e.g. publishing.seo's dependency on
    design.thumbnails).
    """
    try:
        return await get_artifact_by_slug(project_id, slug)
    except Exception:
        return None


async def upsert_artifact(
    project_id: UUID,
    node_key: str,
    artifact_type: str,
    slug: str,
    payload: dict,
    summary: str | None,
    model: str | None,
    dependencies: list[Dependency] | None = None,
) -> Artifact:
    """Called by the Director after an agent's AgentResult comes back ok=True.

    First-time generation and later regeneration both land here (unique on
    project_id+slug). current_version is bumped from whatever's already
    there -- the BEFORE INSERT OR UPDATE OF payload trigger in 001_init.sql
    snapshots each version into artifact_versions automatically. edited_by
    is deliberately cleared: this write came from an agent, not a human, so
    any prior hand-edit marker no longer applies to this new payload.

    `dependencies` (the owning TaskNode's node-level deps) gets mirrored
    into artifact_dependencies -- a separate, artifact-level edge table that
    mark_dependents_stale() actually walks. Without this, that table stays
    empty forever and staleness silently never propagates to anything.
    """
    existing = await try_get_artifact_by_slug(project_id, slug)
    next_version = (existing.current_version + 1) if existing else 1

    def _upsert():
        return (
            get_supabase()
            .table("artifacts")
            .upsert(
                {
                    "project_id": str(project_id),
                    "node_key": node_key,
                    "type": artifact_type,
                    "slug": slug,
                    "current_version": next_version,
                    "payload": payload,
                    "summary": summary,
                    "model": model,
                    "edited_by": None,
                    "is_stale": False,
                    "stale_reason": None,
                },
                on_conflict="project_id,slug",
            )
            .execute()
        )

    response = await asyncio.to_thread(_upsert)
    artifact = Artifact.model_validate(response.data[0])

    if dependencies:
        await _sync_artifact_dependencies(project_id, artifact.id, dependencies)

    return artifact


async def _sync_artifact_dependencies(
    project_id: UUID, artifact_id: UUID, dependencies: list[Dependency]
) -> None:
    for dep in dependencies:
        dep_artifact = await try_get_artifact_by_slug(project_id, slug_for_node_key(dep.node_key))
        if dep_artifact is None:
            # A soft dependency (or a hard one dispatched out of order) whose
            # artifact doesn't exist yet -- nothing to record an edge to.
            continue

        def _upsert_dependency(dep_artifact_id: UUID = dep_artifact.id, kind: str = dep.kind):
            return (
                get_supabase()
                .table("artifact_dependencies")
                .upsert(
                    {
                        "project_id": str(project_id),
                        "artifact_id": str(artifact_id),
                        "depends_on_artifact_id": str(dep_artifact_id),
                        "kind": kind,
                    },
                    on_conflict="artifact_id,depends_on_artifact_id",
                )
                .execute()
            )

        await asyncio.to_thread(_upsert_dependency)


async def update_artifact_payload(
    artifact_id: UUID,
    payload: dict,
    edited_by: str,
) -> Artifact:
    """A human hand-edit via PATCH /artifacts/{id} -- the counterpart to
    upsert_artifact's agent-generated path. model is left untouched (still
    reflects whichever agent/model produced the version this edit builds on).
    """
    existing = await get_artifact(artifact_id)
    next_version = existing.current_version + 1

    def _update():
        return (
            get_supabase()
            .table("artifacts")
            .update(
                {
                    "current_version": next_version,
                    "payload": payload,
                    "edited_by": edited_by,
                    "is_stale": False,
                    "stale_reason": None,
                }
            )
            .eq("id", str(artifact_id))
            .execute()
        )

    response = await asyncio.to_thread(_update)
    return Artifact.model_validate(response.data[0])


async def list_versions(artifact_id: UUID) -> list[dict]:
    def _fetch():
        return (
            get_supabase()
            .table("artifact_versions")
            .select("*")
            .eq("artifact_id", str(artifact_id))
            .order("version", desc=True)
            .execute()
        )

    response = await asyncio.to_thread(_fetch)
    return response.data
