"""Pydantic contracts shared across the director, agents, and routes.

These are data contracts, not logic. Field shapes mirror `migrations/001_init.sql`
and are re-declared in `web/lib/types.ts` for the frontend.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(StrEnum):
    """Lifecycle of a whole project, driven by the Director's LangGraph run."""

    PLANNING = "planning"          # `plan` node hasn't expanded the template into task_nodes yet
    RUNNING = "running"             # `schedule` is actively dispatching ready nodes to agents
    BLOCKED = "blocked"             # a hard-dependency failure blocked the remaining DAG
    AWAITING_GATE = "awaiting_gate"  # paused at a human gate (e.g. outline_review) via interrupt_before
    DONE = "done"                   # `finalize` ran, all required nodes succeeded
    FAILED = "failed"                # `finalize` ran, but a required node never recovered


class NodeStatus(StrEnum):
    """Lifecycle of a single task_nodes row (one DAG node = one artifact to produce)."""

    QUEUED = "queued"        # created by `plan`, dependencies not yet satisfied
    READY = "ready"           # hard dependencies satisfied, eligible for scheduler.ready_set()
    RUNNING = "running"       # currently being executed by an agent
    SUCCEEDED = "succeeded"   # agent returned AgentResult(ok=True); artifact persisted
    FAILED = "failed"         # agent exhausted retries without a valid result
    BLOCKED = "blocked"       # a hard dependency failed; see scheduler.block_hard_dependents
    SKIPPED = "skipped"       # never scheduled, e.g. made moot by a gate rejection


# "hard" deps must succeed before a node can run; "soft" deps are best-effort
# inputs (used if present, ignored if missing/stale) and never block scheduling
# or propagate failure. See scheduler.ready_set / block_hard_dependents.
DependencyKind = Literal["hard", "soft"]


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class CamelModel(BaseModel):
    """Base for every model that's actually part of the HTTP/DB JSON surface
    -- auto-camelCases every field's alias (node_key -> nodeKey, created_at
    -> createdAt, ...) to match web/lib/types.ts, instead of hand-annotating
    Field(alias=...) on each field one at a time (what Dependency used to do
    before this existed -- easy to forget on any new field, which is exactly
    how TaskNode ended up silently NOT matching its own TS type: found via a
    route test hitting a real KeyError on "nodeKey" in the response JSON).

    `populate_by_name=True` means these models still accept plain snake_case
    kwargs from server-side Python code (e.g. `TaskNode(node_key=...)`) --
    the alias only changes what JSON *serialization* looks like, not what
    Python construction requires.

    Deliberately NOT used by TaskEnvelope/AgentResult/ValidationReport --
    those are internal Director<->agent contracts, never serialized to JSON
    for the frontend, so snake_case is fine (and consistent with the rest of
    the Python codebase) there.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Dependency(CamelModel):
    """One edge in a TaskNode's dependency list.

    The DB column (task_nodes.dependencies jsonb, per 001_init.sql) stores
    this as {"nodeKey": "content.outline", "kind": "hard"} -- camelCase, to
    match the frontend's TypeScript shape.
    """

    node_key: str
    kind: DependencyKind = "hard"


class TaskNode(CamelModel):
    """One row of `task_nodes` — a single unit of work in the project DAG.

    `agent` says which specialist (research/content/design/publishing) owns it;
    `capability` says which of that agent's methods to invoke (e.g. "outline",
    "script"). `dependencies` is the adjacency list scheduler.py walks.
    """

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


class Artifact(CamelModel):
    """One row of `artifacts` — the persisted output of a TaskNode.

    `current_version` + `payload` are what the trigger in 001_init.sql snapshots
    into `artifact_versions` on every payload write. `is_stale`/`stale_reason` are
    set by services/staleness.py when a hard upstream dependency changes after
    this artifact was generated (mark_dependents_stale in the migration).
    `edited_by` distinguishes a human hand-edit (e.g. "user") from an agent
    regeneration (e.g. the model name).
    """

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
    """A project's full set of TaskNodes, as the Director holds them in memory."""

    project_id: UUID
    nodes: list[TaskNode]

    def by_key(self) -> dict[str, TaskNode]:
        # TODO: index nodes by node_key for O(1) lookup during scheduling
        raise NotImplementedError


class Project(CamelModel):
    """One row of `projects` — the content idea plus generation params
    (audience, tone, target length, etc.) agents read from in build_context.
    """

    id: UUID
    title: str
    idea: str
    status: ProjectStatus = ProjectStatus.PLANNING
    params: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Director <-> worker contracts
# ---------------------------------------------------------------------------
#
# Workers never talk to each other or query task_nodes/artifacts on their own
# initiative — the Director resolves a TaskNode into a self-contained
# TaskEnvelope, an agent's BaseAgent.run() turns that into an AgentResult, and
# the Director is the only thing that persists it back to Postgres. This pair
# is the seam between director/ and agents/.


class TaskEnvelope(BaseModel):
    """What the Director hands a worker agent to execute one node.

    `input_artifact_slugs` are slugs the agent must resolve itself (via
    services/artifacts.py) to build its context — the envelope carries
    references, not payloads, so it stays cheap to construct and log.
    `word_budget` is only meaningful for script-shaped capabilities; other
    agents ignore it.
    """

    project_id: UUID
    node_key: str
    agent: str
    capability: str
    attempt: int
    input_artifact_slugs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    word_budget: int | None = None
    timeout_s: int = 120


class AgentResult(BaseModel):
    """What a worker agent hands back to the Director.

    Exactly one of (artifact_type/slug/payload) or (error_code/error_message)
    is meaningful, gated by `ok`. The Director persists a successful result via
    services/artifacts.upsert_artifact and feeds a failed one into triage.decide.
    """

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
    """Result of an agent's validate() hook.

    `repair_hint` is the one field that makes BaseAgent.run's retry loop
    smarter than "try again": it's a specific, actionable description of what
    was wrong (e.g. an exact word-count delta, or a list of ungrounded claims)
    that gets folded into the next generation prompt instead of blind retry.
    """

    ok: bool
    failures: list[str] = Field(default_factory=list)
    repair_hint: str | None = None
