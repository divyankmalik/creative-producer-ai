"""Assembles the final `publishing.package` export bundle for a project."""

from __future__ import annotations

from uuid import UUID

from app.services.artifacts import list_artifacts_for_project
from app.services.projects import get_project

DELIVERABLE_SLUG = "publishing-package"


async def build_export(project_id: UUID) -> dict:
    """Bundles everything a project has produced so far -- every artifact's
    payload keyed by slug, plus `deliverable` pulled out separately for
    convenience (the publishing.package artifact, since it's already the
    fully-merged storyboard+SEO output). `deliverable` is None if the
    project hasn't reached that node yet -- export works on partial projects
    too, not just finished ones, same as everything else in this system.
    """
    project = await get_project(project_id)
    artifacts = await list_artifacts_for_project(project_id)

    artifacts_by_slug = {artifact.slug: artifact.payload for artifact in artifacts}

    return {
        "project": {"id": str(project.id), "title": project.title, "idea": project.idea},
        "artifacts": artifacts_by_slug,
        "deliverable": artifacts_by_slug.get(DELIVERABLE_SLUG),
    }
