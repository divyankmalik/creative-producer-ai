"""Unit tests for DesignAgent's two capabilities: visual_language, thumbnails.

Same approach as tests/agents/research and tests/agents/content: mock the I/O
boundaries (get_project, get_artifact_by_slug, generate_structured) so the
suite runs offline/free, while exercising the real (unmocked)
validators/design_rules.py checks against generated drafts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.agents.design import ColorSwatch, DesignAgent, ThumbnailConcept, ThumbnailSet, VisualLanguage
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
        node_key=f"design.{capability}",
        agent="design",
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


def make_outline_payload() -> dict:
    return {
        "title": "Async Standups Explained",
        "sections": [
            {"key": "s1", "title": "Hook", "summary": "Async standups eliminate timezone conflicts.", "weight": 1.0},
            {"key": "s2", "title": "Body", "summary": "They reduce meeting fatigue.", "weight": 2.0},
        ],
    }


def make_visual_language(*, good_contrast: bool = True, missing_role: str | None = None) -> VisualLanguage:
    if missing_role == "text":
        # no "text" role at all -- structural failure
        palette = [
            ColorSwatch(role="background", name="Off White", hex="#FFFFFF"),
            ColorSwatch(role="accent", name="Signal Blue", hex="#3366CC"),
            ColorSwatch(role="highlight", name="Warm Yellow", hex="#FFD700"),
        ]
    elif not good_contrast:
        # both roles present, but the pair is nearly indistinguishable -- contrast failure
        palette = [
            ColorSwatch(role="background", name="Mid Gray", hex="#888888"),
            ColorSwatch(role="text", name="Slightly Darker Gray", hex="#777777"),
            ColorSwatch(role="accent", name="Signal Blue", hex="#3366CC"),
        ]
    else:
        palette = [
            ColorSwatch(role="background", name="Off White", hex="#FFFFFF"),
            ColorSwatch(role="text", name="Charcoal", hex="#000000"),
            ColorSwatch(role="accent", name="Signal Blue", hex="#3366CC"),
        ]

    return VisualLanguage(
        mood="Clean, confident, minimal",
        palette=palette,
        typography="Bold sans-serif headlines, simple body text",
        imagery_style="Flat illustration, high contrast",
        avoid=["stock photo cliches"],
    )


def make_thumbnail_set(*, bad_overlay: bool = False, bad_contrast: bool = False) -> ThumbnailSet:
    """concept_a varies with the flags; concept_b is always valid, so a failure
    is always attributable to exactly one concept.
    """
    concept_a = ThumbnailConcept(
        concept_name="Concept A",
        visual="Close-up of a calendar with every meeting crossed out",
        overlay_text="This Will Change Everything Today" if bad_overlay else "Stop Doing This",
        text_color_hex="#777777" if bad_contrast else "#000000",
        background_color_hex="#888888" if bad_contrast else "#FFFFFF",
    )
    concept_b = ThumbnailConcept(
        concept_name="Concept B",
        visual="Team members working at different times of day",
        overlay_text="No More Meetings",
        text_color_hex="#000000",
        background_color_hex="#FFFFFF",
    )
    return ThumbnailSet(concepts=[concept_a, concept_b])


# ---------------------------------------------------------------------------
# visual_language
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visual_language_happy_path() -> None:
    envelope = make_envelope("visual_language")
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline_payload()
    )
    vl = make_visual_language()

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch("app.agents.design.generate_structured", new_callable=AsyncMock, return_value=vl) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "design_visual_language"
    assert result.slug == "design-visual-language"
    assert result.summary == vl.mood
    assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_visual_language_missing_text_role_triggers_repair() -> None:
    envelope = make_envelope("visual_language")
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline_payload()
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_visual_language(missing_role="text"), make_visual_language()],
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    assert mock_gen.await_args_list[0].kwargs["repair_hint"] is None
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "text" in second_hint


@pytest.mark.asyncio
async def test_visual_language_low_contrast_triggers_repair() -> None:
    envelope = make_envelope("visual_language")
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline_payload()
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_visual_language(good_contrast=False), make_visual_language(good_contrast=True)],
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "contrast" in second_hint.lower()


@pytest.mark.asyncio
async def test_visual_language_exhausts_retries() -> None:
    envelope = make_envelope("visual_language")
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline_payload()
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            return_value=make_visual_language(good_contrast=False),
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert mock_gen.await_count == DesignAgent.max_attempts


# ---------------------------------------------------------------------------
# thumbnails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnails_happy_path() -> None:
    envelope = make_envelope("thumbnails")
    vl_artifact = make_artifact(
        envelope.project_id,
        "design.visual_language",
        "design_visual_language",
        "design-visual-language",
        make_visual_language().model_dump(),
    )
    thumbnails = make_thumbnail_set()

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=vl_artifact),
        patch(
            "app.agents.design.generate_structured", new_callable=AsyncMock, return_value=thumbnails
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "design_thumbnails"
    assert result.slug == "design-thumbnails"
    assert result.summary == "2 thumbnail concepts"
    assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_thumbnails_overlay_violation_triggers_repair() -> None:
    envelope = make_envelope("thumbnails")
    vl_artifact = make_artifact(
        envelope.project_id,
        "design.visual_language",
        "design_visual_language",
        "design-visual-language",
        make_visual_language().model_dump(),
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=vl_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_thumbnail_set(bad_overlay=True), make_thumbnail_set()],
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "Cut" in second_hint and "words" in second_hint


@pytest.mark.asyncio
async def test_thumbnails_contrast_violation_triggers_repair() -> None:
    envelope = make_envelope("thumbnails")
    vl_artifact = make_artifact(
        envelope.project_id,
        "design.visual_language",
        "design_visual_language",
        "design-visual-language",
        make_visual_language().model_dump(),
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=vl_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_thumbnail_set(bad_contrast=True), make_thumbnail_set()],
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "contrast" in second_hint.lower()


@pytest.mark.asyncio
async def test_thumbnails_exhausts_retries() -> None:
    envelope = make_envelope("thumbnails")
    vl_artifact = make_artifact(
        envelope.project_id,
        "design.visual_language",
        "design_visual_language",
        "design-visual-language",
        make_visual_language().model_dump(),
    )

    with (
        patch("app.agents.design.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.design.get_artifact_by_slug", new_callable=AsyncMock, return_value=vl_artifact),
        patch(
            "app.agents.design.generate_structured",
            new_callable=AsyncMock,
            return_value=make_thumbnail_set(bad_overlay=True),
        ) as mock_gen,
    ):
        result = await DesignAgent().run(envelope)

    assert result.ok is False
    assert mock_gen.await_count == DesignAgent.max_attempts
