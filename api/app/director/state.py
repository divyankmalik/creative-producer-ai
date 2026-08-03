"""LangGraph state for the Director graph."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from app.models import TaskNode


class DirectorState(TypedDict):
    """State threaded through plan -> schedule -> gate -> finalize."""

    project_id: UUID
    nodes: list[TaskNode]
    running_node_keys: list[str]
    pending_gate_key: str | None
    max_parallel: int
    done: bool


def initial_state(project_id: UUID, max_parallel: int = 3) -> DirectorState:
    # TODO: build the DirectorState LangGraph starts with, before `plan` expands the template
    raise NotImplementedError
