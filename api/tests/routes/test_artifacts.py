"""Tests for routes/artifacts.py -- TestClient against the real FastAPI app,
service layer (and the agent actually dispatched by regenerate) mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agents.research import ResearchAgent
from app.main import app
from app.models import Artifact, AgentResult, NodeStatus, TaskNode

NOW = datetime.now(timezone.utc)

client = TestClient(app)


def make_artifact(project_id=None, artifact_id=None, *, node_key="research.brief", slug="research-brief") -> Artifact:
    return Artifact(
        id=artifact_id or uuid4(),
        project_id=project_id or uuid4(),
        node_key=node_key,
        type="research_brief",
        slug=slug,
        current_version=1,
        payload={"angle": "a"},
        summary="s",
        is_stale=False,
        created_at=NOW,
        updated_at=NOW,
    )


def make_task_node(project_id, node_key="research.brief", *, agent="research", capability="brief") -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=project_id,
        node_key=node_key,
        agent=agent,
        capability=capability,
        status=NodeStatus.SUCCEEDED,
        dependencies=[],
        params={},
        attempts=0,
        created_at=NOW,
        updated_at=NOW,
    )


def test_get_artifact_returns_200_with_camel_case_body() -> None:
    artifact = make_artifact()

    with patch("app.routes.artifacts.artifacts_service.get_artifact", new_callable=AsyncMock, return_value=artifact):
        response = client.get(f"/artifacts/{artifact.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(artifact.id)
    assert body["nodeKey"] == "research.brief"
    assert body["isStale"] is False


def test_get_artifact_returns_404_when_missing() -> None:
    with patch(
        "app.routes.artifacts.artifacts_service.get_artifact",
        new_callable=AsyncMock,
        side_effect=Exception("no row"),
    ):
        response = client.get(f"/artifacts/{uuid4()}")

    assert response.status_code == 404


def test_patch_artifact_updates_payload_and_reports_stale_dependents() -> None:
    artifact_id = uuid4()
    updated = make_artifact(artifact_id=artifact_id)

    with (
        patch(
            "app.routes.artifacts.artifacts_service.update_artifact_payload",
            new_callable=AsyncMock,
            return_value=updated,
        ) as mock_update,
        patch(
            "app.routes.artifacts.staleness_service.mark_dependents_stale",
            new_callable=AsyncMock,
            return_value=["content-outline", "content-script-s1"],
        ) as mock_stale,
    ):
        response = client.patch(
            f"/artifacts/{artifact_id}",
            json={"payload": {"angle": "new angle"}, "editedBy": "user"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["staleDependents"] == ["content-outline", "content-script-s1"]
    mock_update.assert_awaited_once_with(artifact_id, {"angle": "new angle"}, "user")
    mock_stale.assert_awaited_once()


def test_regenerate_artifact_success_persists_and_marks_dependents_stale() -> None:
    project_id = uuid4()
    artifact_id = uuid4()
    artifact = make_artifact(project_id, artifact_id)
    node = make_task_node(project_id)
    result = AgentResult(
        ok=True, artifact_type="research_brief", slug="research-brief", payload={"angle": "b"}, summary="s2", model="m"
    )

    with (
        patch("app.routes.artifacts.artifacts_service.get_artifact", new_callable=AsyncMock, return_value=artifact),
        patch(
            "app.routes.artifacts.task_nodes_service.get_task_node_by_key",
            new_callable=AsyncMock,
            return_value=node,
        ),
        patch.object(ResearchAgent, "run", new_callable=AsyncMock, return_value=result) as mock_run,
        patch("app.routes.artifacts.artifacts_service.upsert_artifact", new_callable=AsyncMock) as mock_upsert,
        patch("app.routes.artifacts.task_nodes_service.update_task_node", new_callable=AsyncMock) as mock_update_node,
        patch(
            "app.routes.artifacts.staleness_service.mark_dependents_stale", new_callable=AsyncMock, return_value=[]
        ),
    ):
        response = client.post(f"/artifacts/{artifact_id}/regenerate")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["nodeKey"] == "research.brief"
    mock_run.assert_awaited_once()
    mock_upsert.assert_awaited_once()
    mock_update_node.assert_awaited_once_with(node.id, status=NodeStatus.SUCCEEDED)


def test_regenerate_artifact_failure_marks_node_failed_without_persisting() -> None:
    project_id = uuid4()
    artifact_id = uuid4()
    artifact = make_artifact(project_id, artifact_id)
    node = make_task_node(project_id)
    failure = AgentResult(ok=False, error_code="validation_failed", error_message="bad draft")

    with (
        patch("app.routes.artifacts.artifacts_service.get_artifact", new_callable=AsyncMock, return_value=artifact),
        patch(
            "app.routes.artifacts.task_nodes_service.get_task_node_by_key",
            new_callable=AsyncMock,
            return_value=node,
        ),
        patch.object(ResearchAgent, "run", new_callable=AsyncMock, return_value=failure),
        patch("app.routes.artifacts.artifacts_service.upsert_artifact", new_callable=AsyncMock) as mock_upsert,
        patch("app.routes.artifacts.task_nodes_service.update_task_node", new_callable=AsyncMock) as mock_update_node,
    ):
        response = client.post(f"/artifacts/{artifact_id}/regenerate")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    mock_upsert.assert_not_awaited()
    mock_update_node.assert_awaited_once_with(
        node.id, status=NodeStatus.FAILED, last_error="bad draft", increment_attempts=True
    )


def test_get_artifact_versions_maps_rows_to_camel_case() -> None:
    artifact_id = uuid4()
    rows = [
        {"version": 2, "summary": "v2", "edited_by": "user", "model": None, "created_at": NOW},
        {"version": 1, "summary": "v1", "edited_by": None, "model": "gemini-2.5-flash", "created_at": NOW},
    ]

    with patch(
        "app.routes.artifacts.artifacts_service.list_versions", new_callable=AsyncMock, return_value=rows
    ):
        response = client.get(f"/artifacts/{artifact_id}/versions")

    assert response.status_code == 200
    body = response.json()
    assert len(body["versions"]) == 2
    assert body["versions"][0]["version"] == 2
    assert body["versions"][0]["editedBy"] == "user"
    assert body["versions"][1]["model"] == "gemini-2.5-flash"
