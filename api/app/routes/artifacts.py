"""Artifact read/edit/regenerate endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field

from app.director.graph import AGENT_REGISTRY, build_envelope
from app.director.template import slug_for_node_key
from app.models import Artifact, CamelModel, NodeStatus
from app.services import artifacts as artifacts_service
from app.services import staleness as staleness_service
from app.services import task_nodes as task_nodes_service

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class PatchArtifactRequest(CamelModel):
    payload: dict[str, Any]
    edited_by: str


class PatchArtifactResponse(CamelModel):
    artifact: Artifact
    stale_dependents: list[str] = Field(default_factory=list)


class RegenerateArtifactResponse(CamelModel):
    ok: bool
    node_key: str


class ArtifactVersionSummary(CamelModel):
    version: int
    summary: str | None = None
    edited_by: str | None = None
    model: str | None = None
    created_at: datetime


class ArtifactVersionsResponse(CamelModel):
    versions: list[ArtifactVersionSummary]


@router.get("/{artifact_id}", response_model=Artifact)
async def get_artifact(artifact_id: UUID) -> Artifact:
    try:
        return await artifacts_service.get_artifact(artifact_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc


@router.patch("/{artifact_id}", response_model=PatchArtifactResponse)
async def patch_artifact(artifact_id: UUID, request: PatchArtifactRequest) -> PatchArtifactResponse:
    try:
        updated = await artifacts_service.update_artifact_payload(artifact_id, request.payload, request.edited_by)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc

    stale_dependents = await staleness_service.mark_dependents_stale(
        artifact_id, f"'{updated.slug}' was edited by {request.edited_by}"
    )
    return PatchArtifactResponse(artifact=updated, stale_dependents=stale_dependents)


@router.post("/{artifact_id}/regenerate", response_model=RegenerateArtifactResponse)
async def regenerate_artifact(artifact_id: UUID) -> RegenerateArtifactResponse:
    """Deliberately does NOT go through the Director graph -- see
    docs/director.md and the design discussion behind it. A finished graph
    run's checkpoint represents a completed thread; reviving it to redo one
    unrelated node fights LangGraph's execution model for no benefit, since
    GET /projects/{id} already reads straight from these same DB tables, not
    the checkpoint. Regenerating one artifact is a single, isolated unit of
    work -- everything it depends on already exists -- so this just calls
    the owning agent directly, reusing the Director's own envelope-building
    and agent-registry logic rather than duplicating it.
    """
    try:
        artifact = await artifacts_service.get_artifact(artifact_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc

    node = await task_nodes_service.get_task_node_by_key(artifact.project_id, artifact.node_key)

    envelope = build_envelope(artifact.project_id, node)
    agent_cls = AGENT_REGISTRY[node.agent]
    result = await agent_cls().run(envelope)

    if not result.ok:
        await task_nodes_service.update_task_node(
            node.id, status=NodeStatus.FAILED, last_error=result.error_message, increment_attempts=True
        )
        return RegenerateArtifactResponse(ok=False, node_key=node.node_key)

    await artifacts_service.upsert_artifact(
        project_id=artifact.project_id,
        node_key=node.node_key,
        artifact_type=result.artifact_type or node.capability,
        slug=result.slug or slug_for_node_key(node.node_key),
        payload=result.payload or {},
        summary=result.summary,
        model=result.model,
        dependencies=node.dependencies,
    )
    await task_nodes_service.update_task_node(node.id, status=NodeStatus.SUCCEEDED)
    # A regeneration changes content the same way a human edit does -- its
    # own dependents need to know, same as PATCH does.
    await staleness_service.mark_dependents_stale(artifact.id, f"'{artifact.slug}' was regenerated")

    return RegenerateArtifactResponse(ok=True, node_key=node.node_key)


@router.get("/{artifact_id}/versions", response_model=ArtifactVersionsResponse)
async def get_artifact_versions(artifact_id: UUID) -> ArtifactVersionsResponse:
    versions = await artifacts_service.list_versions(artifact_id)
    return ArtifactVersionsResponse(
        versions=[
            ArtifactVersionSummary(
                version=row["version"],
                summary=row.get("summary"),
                edited_by=row.get("edited_by"),
                model=row.get("model"),
                created_at=row["created_at"],
            )
            for row in versions
        ]
    )
