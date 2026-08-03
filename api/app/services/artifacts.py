"""CRUD/query helpers over the artifacts and artifact_versions tables."""

from __future__ import annotations

from uuid import UUID

from app.models import Artifact


async def get_artifact(artifact_id: UUID) -> Artifact:
    # TODO: select from artifacts by id.
    raise NotImplementedError


async def get_artifact_by_slug(project_id: UUID, slug: str) -> Artifact:
    # TODO: select from artifacts by (project_id, slug).
    raise NotImplementedError


async def upsert_artifact(
    project_id: UUID,
    node_key: str,
    artifact_type: str,
    slug: str,
    payload: dict,
    summary: str | None,
    model: str | None,
) -> Artifact:
    # TODO: insert/update artifacts row; the DB trigger snapshots into artifact_versions.
    raise NotImplementedError


async def update_artifact_payload(
    artifact_id: UUID,
    payload: dict,
    edited_by: str,
) -> Artifact:
    # TODO: bump current_version, write payload, set edited_by; trigger snapshots the version.
    raise NotImplementedError


async def list_versions(artifact_id: UUID) -> list[dict]:
    # TODO: select ordered artifact_versions rows for this artifact.
    raise NotImplementedError
