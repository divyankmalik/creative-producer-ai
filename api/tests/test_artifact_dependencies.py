"""Tests for services/artifacts.py's _sync_artifact_dependencies -- the
piece that mirrors a TaskNode's node-level dependencies into the
artifact_dependencies table, which mark_dependents_stale() actually walks.

Isolated from the rest of upsert_artifact by mocking try_get_artifact_by_slug
directly (already covered by its own tests) rather than the full Supabase
chain for the outer artifact write too.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import Artifact, Dependency
from app.services.artifacts import _sync_artifact_dependencies

NOW = datetime.now(timezone.utc)


def make_artifact(project_id, slug) -> Artifact:
    return Artifact(
        id=uuid4(),
        project_id=project_id,
        node_key="content.outline",
        type="content_outline",
        slug=slug,
        current_version=1,
        payload={},
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_writes_an_edge_for_each_resolvable_dependency() -> None:
    project_id = uuid4()
    artifact_id = uuid4()
    dep_artifact = make_artifact(project_id, "content-outline")

    mock_client = MagicMock()

    with (
        patch("app.services.artifacts.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=dep_artifact),
        patch("app.services.artifacts.get_supabase", return_value=mock_client),
    ):
        await _sync_artifact_dependencies(
            project_id, artifact_id, [Dependency(node_key="content.outline", kind="hard")]
        )

    mock_client.table.assert_called_with("artifact_dependencies")
    upsert_call = mock_client.table.return_value.upsert
    upsert_call.assert_called_once()
    payload = upsert_call.call_args.args[0]
    assert payload["artifact_id"] == str(artifact_id)
    assert payload["depends_on_artifact_id"] == str(dep_artifact.id)
    assert payload["kind"] == "hard"
    assert upsert_call.call_args.kwargs["on_conflict"] == "artifact_id,depends_on_artifact_id"


@pytest.mark.asyncio
async def test_skips_dependency_whose_artifact_does_not_exist_yet() -> None:
    """The soft-dependency case (e.g. design.thumbnails not generated yet) --
    nothing to record an edge to, and must not raise.
    """
    project_id = uuid4()
    artifact_id = uuid4()
    mock_client = MagicMock()

    with (
        patch("app.services.artifacts.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch("app.services.artifacts.get_supabase", return_value=mock_client),
    ):
        await _sync_artifact_dependencies(
            project_id, artifact_id, [Dependency(node_key="design.thumbnails", kind="soft")]
        )

    mock_client.table.assert_not_called()


@pytest.mark.asyncio
async def test_writes_one_edge_per_dependency_when_multiple_resolve() -> None:
    project_id = uuid4()
    artifact_id = uuid4()
    outline_artifact = make_artifact(project_id, "content-outline")
    thumbnails_artifact = make_artifact(project_id, "design-thumbnails")

    async def fake_try_get(pid, slug):
        return {"content-outline": outline_artifact, "design-thumbnails": thumbnails_artifact}.get(slug)

    mock_client = MagicMock()

    with (
        patch("app.services.artifacts.try_get_artifact_by_slug", new=fake_try_get),
        patch("app.services.artifacts.get_supabase", return_value=mock_client),
    ):
        await _sync_artifact_dependencies(
            project_id,
            artifact_id,
            [
                Dependency(node_key="content.outline", kind="hard"),
                Dependency(node_key="design.thumbnails", kind="soft"),
            ],
        )

    assert mock_client.table.return_value.upsert.call_count == 2
