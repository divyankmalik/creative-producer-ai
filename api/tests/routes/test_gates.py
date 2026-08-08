"""Tests for routes/gates.py -- TestClient against the real FastAPI app.
_resume_after_gate (the background job) is always mocked: letting it run for
real would try to resume an actual LangGraph checkpoint inside the test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models import NodeStatus, TaskNode

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
