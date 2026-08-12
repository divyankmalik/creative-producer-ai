"""Tests for routes/projects.py -- TestClient against the real FastAPI app,
service layer mocked. _run_director (the background job) is always mocked
too: letting it run for real would try to execute the whole Director graph
inside the test.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import Artifact, NodeStatus, Project, ProjectStatus, TaskNode

NOW = datetime.now(timezone.utc)

client = TestClient(app)


def make_bearer_header(user_id) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "role": "authenticated", "exp": int(time.time()) + 3600},
        get_settings().supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def make_project(project_id, *, status=ProjectStatus.PLANNING) -> Project:
    return Project(
        id=project_id,
        title="Async Standups",
        idea="Why fully-async daily standups quietly kill remote team morale.",
        status=status,
        params={},
        created_at=NOW,
        updated_at=NOW,
    )


def make_task_node(project_id, node_key) -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=project_id,
        node_key=node_key,
        agent="research",
        capability="brief",
        status=NodeStatus.SUCCEEDED,
        dependencies=[],
        params={},
        attempts=0,
        created_at=NOW,
        updated_at=NOW,
    )


def make_artifact(project_id, slug) -> Artifact:
    return Artifact(
        id=uuid4(),
        project_id=project_id,
        node_key="research.brief",
        type="research_brief",
        slug=slug,
        current_version=1,
        payload={"angle": "a"},
        summary="s",
        is_stale=False,
        created_at=NOW,
        updated_at=NOW,
    )


def test_create_project_returns_202_and_schedules_director() -> None:
    project = make_project(uuid4())

    with (
        patch("app.routes.projects.projects_service.create_project", new_callable=AsyncMock, return_value=project),
        patch("app.routes.projects._run_director", new_callable=AsyncMock) as mock_run_director,
    ):
        response = client.post("/projects", json={"title": "T", "idea": "I", "params": {}})

    assert response.status_code == 202
    body = response.json()
    assert body["projectId"] == str(project.id)
    assert body["status"] == "planning"
    mock_run_director.assert_awaited_once_with(project.id)


def test_get_project_returns_detail_with_nodes_and_artifact_summaries() -> None:
    project_id = uuid4()
    project = make_project(project_id, status=ProjectStatus.RUNNING)
    nodes = [make_task_node(project_id, "research.brief")]
    artifacts = [make_artifact(project_id, "research-brief")]

    with (
        patch("app.routes.projects.projects_service.get_project", new_callable=AsyncMock, return_value=project),
        patch(
            "app.routes.projects.task_nodes_service.list_task_nodes", new_callable=AsyncMock, return_value=nodes
        ),
        patch(
            "app.routes.projects.artifacts_service.list_artifacts_for_project",
            new_callable=AsyncMock,
            return_value=artifacts,
        ),
    ):
        response = client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(project_id)
    assert body["status"] == "running"
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["nodeKey"] == "research.brief"
    assert len(body["artifacts"]) == 1
    assert body["artifacts"][0]["slug"] == "research-brief"


def test_get_project_returns_404_when_missing() -> None:
    with patch(
        "app.routes.projects.projects_service.get_project", new_callable=AsyncMock, side_effect=Exception("no row")
    ):
        response = client.get(f"/projects/{uuid4()}")

    assert response.status_code == 404


def test_export_project_wraps_bundle() -> None:
    project_id = uuid4()
    bundle = {"project": {"id": str(project_id)}, "artifacts": {}, "deliverable": None}

    with patch("app.routes.projects.export_service.build_export", new_callable=AsyncMock, return_value=bundle):
        response = client.get(f"/projects/{project_id}/export")

    assert response.status_code == 200
    body = response.json()
    assert body["projectId"] == str(project_id)
    assert body["bundle"] == bundle


def test_create_project_stamps_owner_id_when_signed_in() -> None:
    user_id = uuid4()
    project = make_project(uuid4())

    with (
        patch(
            "app.routes.projects.projects_service.create_project", new_callable=AsyncMock, return_value=project
        ) as mock_create,
        patch("app.routes.projects._run_director", new_callable=AsyncMock),
    ):
        response = client.post(
            "/projects", json={"title": "T", "idea": "I", "params": {}}, headers=make_bearer_header(user_id)
        )

    assert response.status_code == 202
    mock_create.assert_awaited_once_with("T", "I", {}, owner_id=user_id)


def test_create_project_allows_anonymous_creation_with_no_owner() -> None:
    """Real behavior this project has always had, and still has -- project
    creation never required signing in, only Timeline/Export do.
    """
    project = make_project(uuid4())

    with (
        patch(
            "app.routes.projects.projects_service.create_project", new_callable=AsyncMock, return_value=project
        ) as mock_create,
        patch("app.routes.projects._run_director", new_callable=AsyncMock),
    ):
        response = client.post("/projects", json={"title": "T", "idea": "I", "params": {}})

    assert response.status_code == 202
    mock_create.assert_awaited_once_with("T", "I", {}, owner_id=None)


def test_list_my_projects_requires_auth() -> None:
    response = client.get("/projects")

    assert response.status_code == 401


def test_list_my_projects_returns_only_the_callers_projects() -> None:
    user_id = uuid4()
    owned = [make_project(uuid4()), make_project(uuid4(), status=ProjectStatus.DONE)]

    with patch(
        "app.routes.projects.projects_service.list_projects_for_owner",
        new_callable=AsyncMock,
        return_value=owned,
    ) as mock_list:
        response = client.get("/projects", headers=make_bearer_header(user_id))

    assert response.status_code == 200
    body = response.json()
    assert len(body["projects"]) == 2
    assert {p["status"] for p in body["projects"]} == {"planning", "done"}
    mock_list.assert_awaited_once_with(user_id)
