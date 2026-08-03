"""Pydantic contracts shared across the director, agents, and routes.

These are data contracts, not logic. Field shapes mirror `migrations/001_init.sql`
and are re-declared in `web/lib/types.ts` for the frontend.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    AWAITING_GATE = "awaiting_gate"
    DONE = "done"
    FAILED = "failed"


class NodeStatus(StrEnum):
    QUEUED = "queued"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


DependencyKind = Literal["hard", "soft"]


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class Dependency(BaseModel):
    node_key: str
    kind: DependencyKind = "hard"


class TaskNode(BaseModel):
    id: UUID
    project_id: UUID
    node_key: str
    agent: str
    capability: str
    status: NodeStatus = NodeStatus.QUEUED
    dependencies: list[Dependency] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class Artifact(BaseModel):
    id: UUID
    project_id: UUID
    node_key: str
    type: str
    slug: str
    current_version: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    is_stale: bool = False
    stale_reason: str | None = None
    edited_by: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskGraph(BaseModel):
    project_id: UUID
    nodes: list[TaskNode]

    def by_key(self) -> dict[str, TaskNode]:
        # TODO: index nodes by node_key for O(1) lookup during scheduling
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Director <-> worker contracts
# ---------------------------------------------------------------------------


class TaskEnvelope(BaseModel):
    """What the Director hands a worker agent to execute one node."""

    node_key: str
    agent: str
    capability: str
    attempt: int
    input_artifact_slugs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    word_budget: int | None = None
    timeout_s: int = 120


class AgentResult(BaseModel):
    """What a worker agent hands back to the Director."""

    ok: bool
    artifact_type: str | None = None
    slug: str | None = None
    payload: dict[str, Any] | None = None
    summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    model: str | None = None
    latency_ms: int | None = None


class ValidationReport(BaseModel):
    ok: bool
    failures: list[str] = Field(default_factory=list)
    repair_hint: str | None = None
