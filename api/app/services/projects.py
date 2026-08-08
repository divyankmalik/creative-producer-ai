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


async def claim_gate_resume(project_id: UUID) -> bool:
    """Atomically flips a project from AWAITING_GATE to RUNNING and reports
    whether *this* call is the one that did it.

    POST .../gates/{key}/approve isn't naturally idempotent -- a double
    click, a network retry, or two browser tabs can fire two concurrent
    approve requests for the same gate. Without a guard, both independently
    resume the same LangGraph thread, racing two overlapping executions of
    the back half of the DAG against each other. Live-observed effect: task
    node attempts inflated past NODE_MAX_ATTEMPTS (e.g. 6 instead of 3) --
    not a retry-budget bug, just two runs' DB increments interleaving.

    Postgres serializes concurrent UPDATEs on the same row, so exactly one
    concurrent caller's `.eq("status", AWAITING_GATE)` can match; the loser
    gets back zero rows and knows to skip resuming, since the gate is
    already being (or has already been) handled by the winner.
    """

    def _claim():
        return (
            get_supabase()
            .table("projects")
            .update({"status": ProjectStatus.RUNNING.value})
            .eq("id", str(project_id))
            .eq("status", ProjectStatus.AWAITING_GATE.value)
            .execute()
        )

    response = await asyncio.to_thread(_claim)
    return len(response.data) > 0
