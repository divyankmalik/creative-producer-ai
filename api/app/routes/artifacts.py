"""Artifact read/edit/regenerate endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models import Artifact

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class PatchArtifactRequest(BaseModel):
    payload: dict[str, Any]
    edited_by: str


class PatchArtifactResponse(BaseModel):
    artifact: Artifact
    stale_dependents: list[str] = Field(default_factory=list)


class RegenerateArtifactResponse(BaseModel):
    ok: bool
    node_key: str


class ArtifactVersionSummary(BaseModel):
    version: int
    summary: str | None = None
    edited_by: str | None = None
    model: str | None = None
    created_at: datetime


class ArtifactVersionsResponse(BaseModel):
    versions: list[ArtifactVersionSummary]


@router.get("/{artifact_id}", response_model=Artifact)
async def get_artifact(artifact_id: UUID) -> Artifact:
    # TODO: call services/artifacts.py get_artifact(artifact_id).
    raise NotImplementedError


@router.patch("/{artifact_id}", response_model=PatchArtifactResponse)
async def patch_artifact(artifact_id: UUID, request: PatchArtifactRequest) -> PatchArtifactResponse:
    # TODO: services/artifacts.py update_artifact_payload(...), then
    # services/staleness.py mark_dependents_stale(...) and return its result.
    raise NotImplementedError


@router.post("/{artifact_id}/regenerate", response_model=RegenerateArtifactResponse)
async def regenerate_artifact(artifact_id: UUID) -> RegenerateArtifactResponse:
    # TODO: look up the owning task_node, reset it to queued, and resume the
    # Director graph for this project so it re-dispatches the node.
    raise NotImplementedError


@router.get("/{artifact_id}/versions", response_model=ArtifactVersionsResponse)
async def get_artifact_versions(artifact_id: UUID) -> ArtifactVersionsResponse:
    # TODO: call services/artifacts.py list_versions(artifact_id).
    raise NotImplementedError
