"""Unit tests for PublishingAgent's two capabilities: seo, package.

Same approach as tests/agents/research|content|design: mock the I/O
boundaries (get_project, get_artifact_by_slug, try_get_artifact_by_slug,
generate_structured) so the suite runs offline/free, while exercising the
real (unmocked) length/coverage checks against generated drafts.

Two things this suite specifically targets that the other three agents'
suites didn't need to:
  - the SOFT dependency on design.thumbnails (present vs. missing, and a
    malformed-but-present case)
  - `package`'s validate() being unable to self-heal via repair_hint, since
    _generate_package is pure assembly with no LLM/randomness in the loop
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.agents.base import AgentContext
from app.agents.content import Storyboard, StoryboardShot
from app.agents.publishing import PackageSection, PublishingAgent, PublishingPackage, SeoMetadata
from app.llm.client import GEMINI_MODEL
from app.models import Artifact, Project, ProjectStatus, TaskEnvelope

NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def make_project() -> Project:
    return Project(
        id=uuid4(),
        title="Async Standups",
        idea="Why fully-async daily standups quietly kill remote team morale.",
        status=ProjectStatus.PLANNING,
        params={"audience": "engineering managers", "tone": "conversational"},
        created_at=NOW,
        updated_at=NOW,
    )


def make_envelope(capability: str, *, project_id: UUID | None = None) -> TaskEnvelope:
    return TaskEnvelope(
        project_id=project_id or uuid4(),
        node_key=f"publishing.{capability}",
        agent="publishing",
        capability=capability,
        attempt=1,
    )


def make_artifact(project_id: UUID, node_key: str, artifact_type: str, slug: str, payload: dict) -> Artifact:
    return Artifact(
        id=uuid4(),
        project_id=project_id,
        node_key=node_key,
        type=artifact_type,
        slug=slug,
        current_version=1,
        payload=payload,
        created_at=NOW,
        updated_at=NOW,
    )


def make_outline_artifact(project_id: UUID) -> Artifact:
    return make_artifact(
        project_id,
        "content.outline",
        "content_outline",
        "content-outline",
        {
            "title": "Async Standups Explained",
            "sections": [
                {"key": "s1", "title": "Hook", "summary": "Async standups eliminate timezone conflicts."},
                {"key": "s2", "title": "Body", "summary": "They reduce meeting fatigue."},
            ],
        },
    )


def make_thumbnails_artifact(project_id: UUID, *, overlays: list[str] | None = ("Stop Doing This",)) -> Artifact:
    concepts = [{"overlay_text": text} for text in (overlays or [])]
    return make_artifact(
        project_id, "design.thumbnails", "design_thumbnails", "design-thumbnails", {"concepts": concepts}
    )


def make_seo(*, title: str = "Short Title", description: str = "A" * 100) -> SeoMetadata:
    return SeoMetadata(seo_title=title, seo_description=description, tags=["a", "b", "c"])


def make_storyboard(section_keys: list[str]) -> Storyboard:
    return Storyboard(
        shots=[
            StoryboardShot(section_key=key, visual=f"visual for {key}", overlay_text=None, duration_s=5)
            for key in section_keys
        ]
    )


# ---------------------------------------------------------------------------
# seo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seo_happy_path_with_thumbnails() -> None:
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)
    thumbnails_artifact = make_thumbnails_artifact(envelope.project_id, overlays=["Stop Doing This"])
    seo = make_seo(title="Stop Running Daily Standups Wrong")

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.publishing.try_get_artifact_by_slug",
            new_callable=AsyncMock,
            return_value=thumbnails_artifact,
        ),
        patch("app.agents.publishing.generate_structured", new_callable=AsyncMock, return_value=seo) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "publishing_seo"
    assert result.slug == "publishing-seo"
    assert result.summary == seo.seo_title
    assert result.model == GEMINI_MODEL

    prompt_used = mock_gen.call_args.args[0]
    assert "Stop Doing This" in prompt_used
    assert "reinforces or conflicts" in prompt_used


@pytest.mark.asyncio
async def test_seo_happy_path_without_thumbnails() -> None:
    """SOFT dependency missing entirely -- must not raise, must still succeed."""
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)
    seo = make_seo()

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.publishing.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch("app.agents.publishing.generate_structured", new_callable=AsyncMock, return_value=seo) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    prompt_used = mock_gen.call_args.args[0]
    assert "no thumbnails have been generated yet" in prompt_used
    assert "Leave thumbnail_alignment_note as null" in prompt_used


@pytest.mark.asyncio
async def test_seo_thumbnails_present_but_empty_concepts() -> None:
    """SOFT dependency present as a row, but with no concepts -- must not crash."""
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)
    thumbnails_artifact = make_thumbnails_artifact(envelope.project_id, overlays=[])
    seo = make_seo()

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.publishing.try_get_artifact_by_slug",
            new_callable=AsyncMock,
            return_value=thumbnails_artifact,
        ),
        patch("app.agents.publishing.generate_structured", new_callable=AsyncMock, return_value=seo) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    prompt_used = mock_gen.call_args.args[0]
    assert "(none)" in prompt_used


@pytest.mark.asyncio
async def test_seo_title_too_long_triggers_repair() -> None:
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.publishing.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch(
            "app.agents.publishing.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_seo(title="X" * 90), make_seo(title="Short")],
        ) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    assert mock_gen.await_args_list[0].kwargs["repair_hint"] is None
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "60" in second_hint


@pytest.mark.asyncio
async def test_seo_description_too_short_triggers_repair() -> None:
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.publishing.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch(
            "app.agents.publishing.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_seo(description="too short"), make_seo(description="A" * 100)],
        ) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "50" in second_hint


@pytest.mark.asyncio
async def test_seo_description_too_long_triggers_repair() -> None:
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.publishing.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch(
            "app.agents.publishing.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_seo(description="A" * 200), make_seo(description="A" * 100)],
        ) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "160" in second_hint


@pytest.mark.asyncio
async def test_seo_exhausts_retries() -> None:
    envelope = make_envelope("seo")
    outline_artifact = make_outline_artifact(envelope.project_id)

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.publishing.try_get_artifact_by_slug", new_callable=AsyncMock, return_value=None),
        patch(
            "app.agents.publishing.generate_structured",
            new_callable=AsyncMock,
            return_value=make_seo(title="X" * 90),
        ) as mock_gen,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert mock_gen.await_count == PublishingAgent.max_attempts


@pytest.mark.asyncio
async def test_seo_boundary_values_pass() -> None:
    """Exactly at the char caps should pass -- checks are > / <, not >= / <=."""
    agent = PublishingAgent()
    ctx = AgentContext(envelope=make_envelope("seo"))

    at_title_cap = make_seo(title="T" * 60, description="D" * 100)
    report = await agent.validate(ctx, at_title_cap)
    assert report.ok is True

    at_description_floor = make_seo(title="Short", description="D" * 50)
    report = await agent.validate(ctx, at_description_floor)
    assert report.ok is True

    at_description_ceiling = make_seo(title="Short", description="D" * 160)
    report = await agent.validate(ctx, at_description_ceiling)
    assert report.ok is True


# ---------------------------------------------------------------------------
# package
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_package_happy_path() -> None:
    envelope = make_envelope("package")
    storyboard = Storyboard(
        shots=[
            StoryboardShot(section_key="s1", visual="v1", overlay_text="Hook!", duration_s=5),
            StoryboardShot(section_key="s2", visual="v2", overlay_text=None, duration_s=4),
        ]
    )
    seo = make_seo(title="Great Title")
    storyboard_artifact = make_artifact(
        envelope.project_id, "content.storyboard", "content_storyboard", "content-storyboard", storyboard.model_dump()
    )
    seo_artifact = make_artifact(
        envelope.project_id, "publishing.seo", "publishing_seo", "publishing-seo", seo.model_dump()
    )

    async def fake_get_artifact_by_slug(project_id: UUID, slug: str) -> Artifact:
        return {"content-storyboard": storyboard_artifact, "publishing-seo": seo_artifact}[slug]

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new=fake_get_artifact_by_slug),
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "publishing_package"
    assert result.slug == "publishing-package"
    assert result.model is None  # pure assembly, no LLM call
    assert len(result.payload["sections"]) == 2
    # overlay_text=None must survive the mapping, not get coerced/dropped
    s2 = next(s for s in result.payload["sections"] if s["section_key"] == "s2")
    assert s2["overlay_text"] is None


@pytest.mark.asyncio
async def test_package_multiple_missing_sections_reported() -> None:
    agent = PublishingAgent()
    storyboard = make_storyboard(["s1", "s2", "s3"])
    ctx = AgentContext(envelope=make_envelope("package"))
    ctx.input_artifacts["storyboard"] = storyboard

    incomplete = PublishingPackage(
        title="T",
        seo_title="T",
        seo_description="D" * 60,
        tags=["a"],
        sections=[PackageSection(section_key="s1", visual="v", duration_s=5)],
    )

    report = await agent.validate(ctx, incomplete)

    assert report.ok is False
    assert "s2" in report.failures[0]
    assert "s3" in report.failures[0]
    assert report.repair_hint is not None and "s2" in report.repair_hint and "s3" in report.repair_hint


@pytest.mark.asyncio
async def test_package_assembly_bug_does_not_self_heal_and_exhausts_retries() -> None:
    """_generate_package is pure assembly -- if it were ever buggy, retrying
    can't fix it (no LLM/randomness to change between attempts). Simulates
    that by patching _generate_package itself to always return the same
    incomplete result, and confirms the retry loop still runs max_attempts
    times before giving up, rather than looping forever or "succeeding" on
    a fluke.
    """
    envelope = make_envelope("package")
    storyboard = make_storyboard(["s1", "s2"])
    seo = make_seo()
    storyboard_artifact = make_artifact(
        envelope.project_id, "content.storyboard", "content_storyboard", "content-storyboard", storyboard.model_dump()
    )
    seo_artifact = make_artifact(
        envelope.project_id, "publishing.seo", "publishing_seo", "publishing-seo", seo.model_dump()
    )

    async def fake_get_artifact_by_slug(project_id: UUID, slug: str) -> Artifact:
        return {"content-storyboard": storyboard_artifact, "publishing-seo": seo_artifact}[slug]

    buggy_package = PublishingPackage(
        title="T",
        seo_title="T",
        seo_description="D" * 60,
        tags=["a"],
        sections=[PackageSection(section_key="s1", visual="v", duration_s=5)],  # drops s2 every time
    )

    with (
        patch("app.agents.publishing.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.publishing.get_artifact_by_slug", new=fake_get_artifact_by_slug),
        patch(
            "app.agents.publishing.PublishingAgent._generate_package",
            new_callable=AsyncMock,
            return_value=buggy_package,
        ) as mock_generate_package,
    ):
        result = await PublishingAgent().run(envelope)

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert mock_generate_package.await_count == PublishingAgent.max_attempts
