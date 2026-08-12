"""Project lifecycle: create, fetch status, export."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import Field

from app.auth import get_current_user_id, require_user_id
from app.director.graph import build_graph
from app.director.state import initial_state
from app.models import CamelModel, ProjectStatus, TaskNode
from app.services import artifacts as artifacts_service
from app.services import export as export_service
from app.services import projects as projects_service
from app.services import task_nodes as task_nodes_service

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(CamelModel):
    title: str
    idea: str
    params: dict[str, Any] = Field(default_factory=dict)


class CreateProjectResponse(CamelModel):
    project_id: UUID
    status: ProjectStatus


class ArtifactSummary(CamelModel):
    id: UUID
    slug: str
    type: str
    summary: str | None = None
    is_stale: bool = False


class ProjectDetailResponse(CamelModel):
    id: UUID
    title: str
    idea: str
    status: ProjectStatus
    nodes: list[TaskNode]
    artifacts: list[ArtifactSummary]


class ExportResponse(CamelModel):
    project_id: UUID
    bundle: dict[str, Any]


class ProjectSummary(CamelModel):
    id: UUID
    title: str
    status: ProjectStatus
    created_at: datetime


class ListProjectsResponse(CamelModel):
    projects: list[ProjectSummary]


async def _run_director(project_id: UUID) -> None:
    """The actual background job. Runs to completion, to a pause at a gate,
    or to a caught failure -- never left to just vanish silently, since a
    background task's exceptions don't propagate anywhere a client could see.
    """
    try:
        async with build_graph() as graph:
            config = {"configurable": {"thread_id": str(project_id)}}
            await graph.ainvoke(initial_state(project_id), config=config)
    except Exception as exc:
        # Best-effort: don't let a failure to *record* the failure mask the
        # original one. No structured logging exists in this project yet --
        # this is the one place an unexpected crash would otherwise vanish
        # with zero trace, which is worse than a bare print.
        print(f"[director] project {project_id} crashed: {exc!r}")
        try:
            await projects_service.update_project_status(project_id, ProjectStatus.FAILED)
        except Exception:
            pass


@router.post("", status_code=202, response_model=CreateProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    background_tasks: BackgroundTasks,
    owner_id: UUID | None = Depends(get_current_user_id),
) -> CreateProjectResponse:
    # owner_id is None for anonymous requests (no/invalid session token) --
    # creation has always worked signed-out and still does; see
    # services/projects.create_project.
    project = await projects_service.create_project(request.title, request.idea, request.params, owner_id=owner_id)
    background_tasks.add_task(_run_director, project.id)
    return CreateProjectResponse(project_id=project.id, status=project.status)


@router.get("", response_model=ListProjectsResponse)
async def list_my_projects(owner_id: UUID = Depends(require_user_id)) -> ListProjectsResponse:
    """Requires a valid session (unlike every other route on this router,
    which stay reachable signed out) -- there's no anonymous version of
    "my projects" to fall back to.
    """
    projects = await projects_service.list_projects_for_owner(owner_id)
    return ListProjectsResponse(
        projects=[
            ProjectSummary(id=p.id, title=p.title, status=p.status, created_at=p.created_at) for p in projects
        ]
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: UUID) -> ProjectDetailResponse:
    try:
        project = await projects_service.get_project(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc

    nodes = await task_nodes_service.list_task_nodes(project_id)
    artifacts = await artifacts_service.list_artifacts_for_project(project_id)

    return ProjectDetailResponse(
        id=project.id,
        title=project.title,
        idea=project.idea,
        status=project.status,
        nodes=nodes,
        artifacts=[
            ArtifactSummary(
                id=artifact.id,
                slug=artifact.slug,
                type=artifact.type,
                summary=artifact.summary,
                is_stale=artifact.is_stale,
            )
            for artifact in artifacts
        ],
    )


@router.get("/{project_id}/export", response_model=ExportResponse)
async def export_project(project_id: UUID) -> ExportResponse:
    bundle = await export_service.build_export(project_id)
    return ExportResponse(project_id=project_id, bundle=bundle)
