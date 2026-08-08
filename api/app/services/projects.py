"""CRUD/query helpers over the projects table."""

from __future__ import annotations

import asyncio
from uuid import UUID

from typing import Any

from app.db import get_supabase
from app.models import Project, ProjectStatus


async def create_project(title: str, idea: str, params: dict[str, Any]) -> Project:
    """Called by POST /projects. Row starts at the model's default status
    (PLANNING) -- plan_node is what flips it to RUNNING once the Director
    picks it up.
    """

    def _insert():
        return get_supabase().table("projects").insert({"title": title, "idea": idea, "params": params}).execute()

    response = await asyncio.to_thread(_insert)
    return Project.model_validate(response.data[0])


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
