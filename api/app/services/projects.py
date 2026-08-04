"""CRUD/query helpers over the projects table."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.db import get_supabase
from app.models import Project


async def get_project(project_id: UUID) -> Project:
    def _fetch():
        return get_supabase().table("projects").select("*").eq("id", str(project_id)).single().execute()

    response = await asyncio.to_thread(_fetch)
    return Project.model_validate(response.data)
