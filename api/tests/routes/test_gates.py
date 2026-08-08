"""Tests for routes/gates.py -- TestClient against the real FastAPI app.
_resume_after_gate (the background job) is always mocked: letting it run for
real would try to resume an actual LangGraph checkpoint inside the test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import NodeStatus, ProjectStatus, TaskNode
from app.routes.gates import _resume_after_gate

NOW = datetime.now(timezone.utc)

client = TestClient(app)


def make_task_node(project_id, node_key) -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=project_id,
        node_key=node_key,
        agent="content",
        capability="script",
        status=NodeStatus.QUEUED,
        dependencies=[],
        params={},
        attempts=0,
        created_at=NOW,
        updated_at=NOW,
    )


def test_approve_gate_reports_the_nodes_it_was_blocking() -> None:
    project_id = uuid4()
    nodes = [
        make_task_node(project_id, "content.outline"),
        make_task_node(project_id, "content.script.s1"),
        make_task_node(project_id, "content.script.s2"),
    ]

    with (
        patch("app.routes.gates.list_task_nodes", new_callable=AsyncMock, return_value=nodes),
        patch("app.routes.gates.claim_gate_resume", new_callable=AsyncMock, return_value=True),
        patch("app.routes.gates._resume_after_gate", new_callable=AsyncMock) as mock_resume,
    ):
        response = client.post(f"/projects/{project_id}/gates/outline_review/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert set(body["resumedNodeKeys"]) == {"content.script.s1", "content.script.s2"}
    mock_resume.assert_awaited_once_with(project_id, "outline_review")


def test_approve_gate_returns_404_for_unknown_gate() -> None:
    response = client.post(f"/projects/{uuid4()}/gates/not_a_real_gate/approve")

    assert response.status_code == 404


def test_approve_gate_skips_resume_when_claim_loses() -> None:
    """Regression test for a real bug found via live testing: two concurrent
    approve requests (a double click, in the live case) both resumed the
    same LangGraph thread, racing two overlapping executions of the DAG and
    inflating task_nodes.attempts past NODE_MAX_ATTEMPTS (6 instead of 3).
    claim_gate_resume's atomic conditional UPDATE means only one concurrent
    caller should ever schedule _resume_after_gate -- this simulates the
    loser of that race.
    """
    project_id = uuid4()
    nodes = [make_task_node(project_id, "content.script.s1")]

    with (
        patch("app.routes.gates.list_task_nodes", new_callable=AsyncMock, return_value=nodes),
        patch("app.routes.gates.claim_gate_resume", new_callable=AsyncMock, return_value=False) as mock_claim,
        patch("app.routes.gates._resume_after_gate", new_callable=AsyncMock) as mock_resume,
    ):
        response = client.post(f"/projects/{project_id}/gates/outline_review/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True  # the gate genuinely is approved, whether or not THIS call drove the resume
    mock_claim.assert_awaited_once_with(project_id)
    mock_resume.assert_not_called()  # the actual point of the test -- no second resume scheduled


@pytest.mark.asyncio
async def test_resume_after_gate_marks_project_failed_on_crash() -> None:
    """Regression test for a real bug found via live testing: a transient
    error outside agent execution (e.g. WinError 10035 from the
    checkpointer's own DB write, on Windows) can kill ainvoke() entirely,
    mid-tick -- not caught by schedule_node's own
    asyncio.gather(return_exceptions=True), since that only wraps agent
    calls. Before this fix, the project silently stayed "running" forever:
    any node mid-dispatch at that instant was permanently stuck "running"
    with nothing left to ever finish it.
    """
    project_id = uuid4()

    class _CrashesOnEnter:
        async def __aenter__(self):
            raise RuntimeError("checkpointer write failed: WinError 10035")

        async def __aexit__(self, *args: object) -> bool:
            return False

    with (
        patch("app.routes.gates.build_graph", return_value=_CrashesOnEnter()),
        patch("app.routes.gates.projects_service.update_project_status", new_callable=AsyncMock) as mock_status,
    ):
        await _resume_after_gate(project_id, "outline_review")  # must not raise

    mock_status.assert_awaited_once_with(project_id, ProjectStatus.FAILED)
