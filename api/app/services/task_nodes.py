"""CRUD/query helpers over the task_nodes table.

Not part of the original scaffold's file list -- added because the Director
genuinely can't function without a place to persist/read task_nodes rows,
the same way agents needed services/artifacts.py and services/projects.py.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.db import get_supabase
from app.director.template import NodeTemplate
from app.models import NodeStatus, TaskNode


async def create_task_nodes(project_id: UUID, templates: list[NodeTemplate]) -> list[TaskNode]:
    """Bulk-insert one task_nodes row per (already-expanded) template entry.

    Called once by `plan_node`, after director.template.expand_template has
    turned content.script.sN into concrete s1..sN entries.
    """

    def _insert():
        rows = [
            {
                "project_id": str(project_id),
                "node_key": template.node_key,
                "agent": template.agent,
                "capability": template.capability,
                "status": NodeStatus.QUEUED.value,
                # DB column is camelCase jsonb (see models.Dependency's docstring).
                "dependencies": [
                    {"nodeKey": dep.node_key, "kind": dep.kind} for dep in template.dependencies
                ],
                "params": {},
            }
            for template in templates
        ]
        return get_supabase().table("task_nodes").insert(rows).execute()

    response = await asyncio.to_thread(_insert)
    return [TaskNode.model_validate(row) for row in response.data]


async def list_task_nodes(project_id: UUID) -> list[TaskNode]:
    def _fetch():
        return get_supabase().table("task_nodes").select("*").eq("project_id", str(project_id)).execute()

    response = await asyncio.to_thread(_fetch)
    return [TaskNode.model_validate(row) for row in response.data]


async def update_task_node(
    node_id: UUID,
    *,
    status: NodeStatus | None = None,
    last_error: str | None = None,
    increment_attempts: bool = False,
) -> TaskNode:
    """Partial update of one task_nodes row -- pass only what changed.

    `increment_attempts` does a read-then-write (Supabase's .update() takes
    literal values, not SQL expressions like `attempts = attempts + 1`).
    That's a real race window under concurrent writers to the *same* node,
    but the Director never dispatches the same node twice concurrently, so
    it's an acceptable tradeoff here rather than reaching for a Postgres
    function for one counter.
    """

    def _fetch_current_attempts() -> int:
        response = get_supabase().table("task_nodes").select("attempts").eq("id", str(node_id)).single().execute()
        return response.data["attempts"]

    def _update(payload: dict):
        return get_supabase().table("task_nodes").update(payload).eq("id", str(node_id)).execute()

    payload: dict = {}
    if status is not None:
        payload["status"] = status.value
    if last_error is not None:
        payload["last_error"] = last_error
    if increment_attempts:
        current_attempts = await asyncio.to_thread(_fetch_current_attempts)
        payload["attempts"] = current_attempts + 1

    response = await asyncio.to_thread(_update, payload)
    return TaskNode.model_validate(response.data[0])
