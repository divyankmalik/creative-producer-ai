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
    # Gate keys a human has approved (via the future POST .../gates/{key}/approve
    # route, which would resume the checkpointed graph with this updated).
    # Without this, schedule_node would have no way to remember "outline_review
    # was already approved" across separate graph invocations/resumes.
    approved_gates: list[str]
    max_parallel: int
    done: bool


def initial_state(project_id: UUID, max_parallel: int = 3) -> DirectorState:
    return DirectorState(
        project_id=project_id,
        nodes=[],
        running_node_keys=[],
        pending_gate_key=None,
        approved_gates=[],
        max_parallel=max_parallel,
        done=False,
    )
