"""Project lifecycle: create, fetch status, export."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.models import ProjectStatus, TaskNode

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    title: str
    idea: str
    params: dict[str, Any] = Field(default_factory=dict)


class CreateProjectResponse(BaseModel):
    project_id: UUID
    status: ProjectStatus


class ArtifactSummary(BaseModel):
    id: UUID
    slug: str
    type: str
    summary: str | None = None
    is_stale: bool = False


class ProjectDetailResponse(BaseModel):
    id: UUID
    title: str
    idea: str
    status: ProjectStatus
    nodes: list[TaskNode]
    artifacts: list[ArtifactSummary]


class ExportResponse(BaseModel):
    project_id: UUID
    bundle: dict[str, Any]


@router.post("", status_code=202, response_model=CreateProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    background_tasks: BackgroundTasks,
) -> CreateProjectResponse:
    # TODO: insert a `projects` row, then schedule the Director graph run
    # (director/graph.py build_graph().ainvoke(...)) via background_tasks.
    raise NotImplementedError


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: UUID) -> ProjectDetailResponse:
    # TODO: fetch project + task_nodes + artifact summaries for the poll loop.
    raise NotImplementedError


@router.get("/{project_id}/export", response_model=ExportResponse)
async def export_project(project_id: UUID) -> ExportResponse:
    # TODO: call services/export.py build_export(project_id).
    raise NotImplementedError
