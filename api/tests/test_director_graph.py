"""Tests for director/graph.py's node functions.

Same approach as tests/agents/*: mock the I/O boundaries (get_project,
update_project_status, task_nodes_service.*, artifacts_service.*, and each
agent's .run()) so this runs offline/free, while exercising the real
(unmocked) scheduler.ready_set / block_hard_dependents / triage.decide logic
each node function actually calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.agents.content import ContentAgent
from app.agents.design import DesignAgent
from app.agents.research import ResearchAgent
from app.director.graph import (
    _build_envelope,
    finalize_node,
    gate_node,
    plan_node,
    route_after_schedule,
    schedule_node,
)
from app.director.state import initial_state
from app.director.triage import NODE_MAX_ATTEMPTS, Decision
from app.models import AgentResult, Dependency, NodeStatus, Project, ProjectStatus, TaskNode

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def make_project(*, params: dict | None = None) -> Project:
    return Project(
        id=uuid4(),
        title="Async Standups",
        idea="Why fully-async daily standups quietly kill remote team morale.",
        status=ProjectStatus.PLANNING,
        params=params or {},
        created_at=NOW,
        updated_at=NOW,
    )


def make_task_node(
    project_id: UUID,
    node_key: str,
    agent: str,
    capability: str,
    *,
    status: NodeStatus = NodeStatus.QUEUED,
    dependencies: list[Dependency] | None = None,
    attempts: int = 0,
) -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=project_id,
        node_key=node_key,
        agent=agent,
        capability=capability,
        status=status,
        dependencies=dependencies or [],
        params={},
        attempts=attempts,
        created_at=NOW,
        updated_at=NOW,
    )


# ---------------------------------------------------------------------------
# plan_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_node_expands_template_and_marks_project_running() -> None:
    project_id = uuid4()
    project = make_project(params={"section_count": 2})
    state = initial_state(project_id)
    fabricated_nodes = [make_task_node(project_id, "research.brief", "research", "brief")]

    with (
        patch("app.director.graph.get_project", new_callable=AsyncMock, return_value=project),
        patch(
            "app.director.graph.task_nodes_service.create_task_nodes",
            new_callable=AsyncMock,
            return_value=fabricated_nodes,
        ) as mock_create,
        patch("app.director.graph.update_project_status", new_callable=AsyncMock) as mock_status,
    ):
        result_state = await plan_node(state)

    assert result_state["nodes"] == fabricated_nodes
    mock_status.assert_awaited_once_with(project_id, ProjectStatus.RUNNING)

    templates_passed = mock_create.call_args.args[1]
    script_templates = [t for t in templates_passed if t.node_key.startswith("content.script.")]
    assert len(script_templates) == 2  # honored project.params["section_count"]


# ---------------------------------------------------------------------------
# schedule_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_node_dispatches_ready_node_and_advances_on_success() -> None:
    project_id = uuid4()
    brief = make_task_node(project_id, "research.brief", "research", "brief")
    outline = make_task_node(
        project_id, "content.outline", "content", "outline",
        dependencies=[Dependency(node_key="research.brief", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [brief, outline]

    result = AgentResult(ok=True, artifact_type="research_brief", slug="research-brief", payload={}, summary="s", model="m")

    with (
        patch.object(ResearchAgent, "run", new_callable=AsyncMock, return_value=result) as mock_run,
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock) as mock_upsert,
    ):
        result_state = await schedule_node(state)

    assert brief.status == NodeStatus.SUCCEEDED
    assert outline.status == NodeStatus.QUEUED  # hard dependency not yet met -- never dispatched
    mock_run.assert_awaited_once()
    mock_upsert.assert_awaited_once()
    assert result_state["done"] is False


@pytest.mark.asyncio
async def test_schedule_node_retries_failure_under_attempt_budget() -> None:
    project_id = uuid4()
    node = make_task_node(project_id, "research.brief", "research", "brief", attempts=0)
    state = initial_state(project_id)
    state["nodes"] = [node]
    failure = AgentResult(ok=False, error_code="validation_failed", error_message="bad draft")

    with (
        patch.object(ResearchAgent, "run", new_callable=AsyncMock, return_value=failure),
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock) as mock_update,
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock) as mock_upsert,
    ):
        await schedule_node(state)

    assert node.status == NodeStatus.QUEUED  # RETRY -> eligible again next tick
    mock_upsert.assert_not_awaited()
    last_call = mock_update.call_args_list[-1]
    assert last_call.kwargs.get("increment_attempts") is True


@pytest.mark.asyncio
async def test_schedule_node_halts_and_blocks_hard_dependents() -> None:
    project_id = uuid4()
    outline = make_task_node(project_id, "content.outline", "content", "outline", attempts=NODE_MAX_ATTEMPTS)
    downstream = make_task_node(
        project_id, "design.visual_language", "design", "visual_language",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [outline, downstream]
    failure = AgentResult(ok=False, error_code="validation_failed", error_message="bad")

    with (
        patch.object(ContentAgent, "run", new_callable=AsyncMock, return_value=failure),
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock),
    ):
        result_state = await schedule_node(state)

    assert outline.status == NodeStatus.FAILED
    assert downstream.status == NodeStatus.BLOCKED
    assert result_state["done"] is True  # both nodes now terminal


@pytest.mark.asyncio
async def test_schedule_node_fail_soft_skips_dependents_and_still_reaches_done() -> None:
    """FAIL_SOFT is unreachable via any current agent's real error_code, so
    this forces the decision via a patch on decide() to prove two things:
    the cascade uses SKIPPED (not BLOCKED), and -- the actual point of the
    fix -- the project still reaches done=True instead of infinite-looping
    schedule_node with dependents stuck QUEUED forever.
    """
    project_id = uuid4()
    node = make_task_node(project_id, "design.visual_language", "design", "visual_language", attempts=NODE_MAX_ATTEMPTS)
    downstream = make_task_node(
        project_id, "design.thumbnails", "design", "thumbnails",
        dependencies=[Dependency(node_key="design.visual_language", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [node, downstream]
    failure = AgentResult(ok=False, error_code="some_future_non_fatal_code", error_message="bad")

    with (
        patch.object(DesignAgent, "run", new_callable=AsyncMock, return_value=failure),
        patch("app.director.graph.decide", return_value=Decision.FAIL_SOFT),
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock),
    ):
        result_state = await schedule_node(state)

    assert node.status == NodeStatus.FAILED
    assert downstream.status == NodeStatus.SKIPPED  # not BLOCKED, and critically not left QUEUED
    assert result_state["done"] is True  # both terminal -- no infinite loop


@pytest.mark.asyncio
async def test_schedule_node_pauses_at_unapproved_gate() -> None:
    project_id = uuid4()
    outline = make_task_node(project_id, "content.outline", "content", "outline", status=NodeStatus.SUCCEEDED)
    script = make_task_node(
        project_id, "content.script.s1", "content", "script",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [outline, script]
    state["approved_gates"] = []

    with (
        patch.object(ContentAgent, "run", new_callable=AsyncMock) as mock_run,
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
    ):
        result_state = await schedule_node(state)

    assert result_state["pending_gate_key"] == "outline_review"
    assert script.status == NodeStatus.QUEUED
    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_node_gated_node_does_not_starve_unrelated_ready_work() -> None:
    """Regression test for a real bug caught during live testing: with
    max_parallel=1, a gated node listed before an unrelated ready node would
    consume the only slot and get filtered out afterward, leaving nothing
    dispatched even though the unrelated node was genuinely ready.
    """
    project_id = uuid4()
    outline = make_task_node(project_id, "content.outline", "content", "outline", status=NodeStatus.SUCCEEDED)
    # content.script.s1 listed first so it would win the old capped-then-filtered race
    script = make_task_node(
        project_id, "content.script.s1", "content", "script",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
    )
    visual_language = make_task_node(
        project_id, "design.visual_language", "design", "visual_language",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [outline, script, visual_language]
    state["max_parallel"] = 1  # only one slot -- the scenario that exposes the bug
    state["approved_gates"] = []

    result = AgentResult(ok=True, artifact_type="design_visual_language", slug="design-visual-language", payload={}, summary="s", model="m")

    with (
        patch.object(ContentAgent, "run", new_callable=AsyncMock) as mock_content_run,
        patch.object(DesignAgent, "run", new_callable=AsyncMock, return_value=result) as mock_design_run,
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock),
    ):
        result_state = await schedule_node(state)

    assert visual_language.status == NodeStatus.SUCCEEDED  # dispatched despite the gated node's slot
    assert script.status == NodeStatus.QUEUED  # correctly held back by the gate
    assert result_state["pending_gate_key"] == "outline_review"
    mock_design_run.assert_awaited_once()
    mock_content_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_node_proceeds_once_gate_is_approved() -> None:
    project_id = uuid4()
    outline = make_task_node(project_id, "content.outline", "content", "outline", status=NodeStatus.SUCCEEDED)
    script = make_task_node(
        project_id, "content.script.s1", "content", "script",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
    )
    state = initial_state(project_id)
    state["nodes"] = [outline, script]
    state["approved_gates"] = ["outline_review"]

    result = AgentResult(ok=True, artifact_type="content_script", slug="content-script-s1", payload={}, summary="s", model="m")

    with (
        patch.object(ContentAgent, "run", new_callable=AsyncMock, return_value=result) as mock_run,
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock),
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock),
    ):
        result_state = await schedule_node(state)

    assert script.status == NodeStatus.SUCCEEDED
    assert result_state["pending_gate_key"] is None
    mock_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_schedule_node_marks_done_when_nothing_left_to_schedule() -> None:
    project_id = uuid4()
    node = make_task_node(project_id, "research.brief", "research", "brief", status=NodeStatus.SUCCEEDED)
    state = initial_state(project_id)
    state["nodes"] = [node]

    result_state = await schedule_node(state)  # ready_set() returns [] -- no mocking needed

    assert result_state["done"] is True


@pytest.mark.asyncio
async def test_schedule_node_handles_agent_exception_without_crashing() -> None:
    project_id = uuid4()
    node = make_task_node(project_id, "research.brief", "research", "brief", attempts=0)
    state = initial_state(project_id)
    state["nodes"] = [node]

    with (
        patch.object(ResearchAgent, "run", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
        patch("app.director.graph.task_nodes_service.update_task_node", new_callable=AsyncMock) as mock_update,
        patch("app.director.graph.artifacts_service.upsert_artifact", new_callable=AsyncMock) as mock_upsert,
    ):
        await schedule_node(state)  # must not raise

    assert node.status == NodeStatus.QUEUED  # attempts=0 -> RETRY, not a crash
    mock_upsert.assert_not_awaited()
    last_call = mock_update.call_args_list[-1]
    assert "boom" in (last_call.kwargs.get("last_error") or "")


# ---------------------------------------------------------------------------
# gate_node / finalize_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_node_clears_pending_gate_key() -> None:
    state = initial_state(uuid4())
    state["pending_gate_key"] = "outline_review"

    result_state = await gate_node(state)

    assert result_state["pending_gate_key"] is None


@pytest.mark.asyncio
async def test_finalize_node_marks_project_done_when_no_failures() -> None:
    project_id = uuid4()
    node = make_task_node(project_id, "research.brief", "research", "brief", status=NodeStatus.SUCCEEDED)
    state = initial_state(project_id)
    state["nodes"] = [node]

    with patch("app.director.graph.update_project_status", new_callable=AsyncMock) as mock_status:
        result_state = await finalize_node(state)

    mock_status.assert_awaited_once_with(project_id, ProjectStatus.DONE)
    assert result_state["done"] is True


@pytest.mark.asyncio
async def test_finalize_node_marks_project_failed_when_any_node_failed_or_blocked() -> None:
    project_id = uuid4()
    ok_node = make_task_node(project_id, "research.brief", "research", "brief", status=NodeStatus.SUCCEEDED)
    bad_node = make_task_node(project_id, "content.outline", "content", "outline", status=NodeStatus.FAILED)
    state = initial_state(project_id)
    state["nodes"] = [ok_node, bad_node]

    with patch("app.director.graph.update_project_status", new_callable=AsyncMock) as mock_status:
        await finalize_node(state)

    mock_status.assert_awaited_once_with(project_id, ProjectStatus.FAILED)


# ---------------------------------------------------------------------------
# route_after_schedule (pure)
# ---------------------------------------------------------------------------


def test_route_after_schedule_gate_takes_priority_even_if_done() -> None:
    state = initial_state(uuid4())
    state["pending_gate_key"] = "outline_review"
    state["done"] = True
    assert route_after_schedule(state) == "gate"


def test_route_after_schedule_finalize_when_done() -> None:
    state = initial_state(uuid4())
    state["done"] = True
    assert route_after_schedule(state) == "finalize"


def test_route_after_schedule_defaults_to_schedule() -> None:
    state = initial_state(uuid4())
    assert route_after_schedule(state) == "schedule"


# ---------------------------------------------------------------------------
# _build_envelope (pure, no I/O)
# ---------------------------------------------------------------------------


def test_build_envelope_derives_section_key_for_script_nodes() -> None:
    project_id = uuid4()
    node = make_task_node(
        project_id, "content.script.s2", "content", "script",
        dependencies=[Dependency(node_key="content.outline", kind="hard")],
        attempts=1,
    )

    envelope = _build_envelope(project_id, node)

    assert envelope.params["section_key"] == "s2"
    assert envelope.input_artifact_slugs == ["content-outline"]
    assert envelope.attempt == 2  # attempts(1) + 1
    assert envelope.word_budget is None  # ContentAgent computes its own fallback


def test_build_envelope_input_slugs_include_soft_dependencies() -> None:
    project_id = uuid4()
    node = make_task_node(
        project_id, "publishing.seo", "publishing", "seo",
        dependencies=[
            Dependency(node_key="content.outline", kind="hard"),
            Dependency(node_key="design.thumbnails", kind="soft"),
        ],
    )

    envelope = _build_envelope(project_id, node)

    assert set(envelope.input_artifact_slugs) == {"content-outline", "design-thumbnails"}
