"""Assembles the final `publishing.package` export bundle for a project."""

from __future__ import annotations

from uuid import UUID


async def build_export(project_id: UUID) -> dict:
    # TODO: gather all artifacts for the project into a single downloadable bundle
    # (script, storyboard, thumbnails, seo metadata).
    raise NotImplementedError
