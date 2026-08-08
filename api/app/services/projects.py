"""CRUD/query helpers over the projects table."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.db import get_supabase
from app.models import Project, ProjectStatus


async def get_project(project_id: UUID) -> Project:
    def _fetch():
        return get_supabase().table("projects").select("*").eq("id", str(project_id)).single().execute()

    response = await asyncio.to_thread(_fetch)
    return Project.model_validate(response.data)


async def update_project_status(project_id: UUID, status: ProjectStatus) -> Project:
    """Called by the Director at plan time (-> RUNNING) and finalize time
    (-> DONE/FAILED), and will be called by schedule_node (-> AWAITING_GATE)
    once a gate route is in place.
    """

    def _update():
        return (
            get_supabase()
            .table("projects")
            .update({"status": status.value})
            .eq("id", str(project_id))
            .execute()
        )

    response = await asyncio.to_thread(_update)
    return Project.model_validate(response.data[0])
