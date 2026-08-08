"""Tests for services/export.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models import Artifact, Project, ProjectStatus
from app.services.export import build_export

NOW = datetime.now(timezone.utc)


def make_project(project_id) -> Project:
    return Project(
        id=project_id,
        title="Async Standups",
        idea="Why fully-async daily standups quietly kill remote team morale.",
        status=ProjectStatus.RUNNING,
        params={},
        created_at=NOW,
        updated_at=NOW,
    )


def make_artifact(project_id, slug, payload) -> Artifact:
    return Artifact(
        id=uuid4(),
        project_id=project_id,
        node_key="x",
        type="x",
        slug=slug,
        current_version=1,
        payload=payload,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_build_export_bundles_every_artifact_by_slug() -> None:
    project_id = uuid4()
    artifacts = [
        make_artifact(project_id, "research-brief", {"angle": "a"}),
        make_artifact(project_id, "content-outline", {"title": "t"}),
    ]

    with (
        patch("app.services.export.get_project", new_callable=AsyncMock, return_value=make_project(project_id)),
        patch(
            "app.services.export.list_artifacts_for_project", new_callable=AsyncMock, return_value=artifacts
        ),
    ):
        bundle = await build_export(project_id)

    assert bundle["project"]["id"] == str(project_id)
    assert bundle["artifacts"]["research-brief"] == {"angle": "a"}
    assert bundle["artifacts"]["content-outline"] == {"title": "t"}
    assert bundle["deliverable"] is None  # no publishing-package yet


@pytest.mark.asyncio
async def test_build_export_pulls_out_deliverable_when_present() -> None:
    project_id = uuid4()
    package_payload = {"title": "Final", "sections": []}
    artifacts = [
        make_artifact(project_id, "research-brief", {"angle": "a"}),
        make_artifact(project_id, "publishing-package", package_payload),
    ]

    with (
        patch("app.services.export.get_project", new_callable=AsyncMock, return_value=make_project(project_id)),
        patch(
            "app.services.export.list_artifacts_for_project", new_callable=AsyncMock, return_value=artifacts
        ),
    ):
        bundle = await build_export(project_id)

    assert bundle["deliverable"] == package_payload
    assert bundle["artifacts"]["publishing-package"] == package_payload
