"""Unit tests for ContentAgent's three capabilities: outline, script, storyboard.

Same approach as tests/agents/research: mock the I/O boundaries (get_project,
get_artifact_by_slug, generate_structured) so the suite runs offline/free,
while exercising the real (unmocked) validators against generated drafts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.agents.content import (
    ContentAgent,
    Outline,
    OutlineSection,
    Script,
    ScriptDraft,
    Storyboard,
    StoryboardShot,
    _section_word_budget,
)
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
        # section_count: 2 matches make_outline()/make_bad_key_outline()'s
        # section count -- must agree, since ContentAgent._validate_outline
        # now enforces len(outline.sections) == project.params["section_count"].
        params={
            "audience": "engineering managers",
            "tone": "conversational",
            "total_seconds": 180,
            "section_count": 2,
        },
        created_at=NOW,
        updated_at=NOW,
    )


def make_envelope(
    capability: str,
    *,
    project_id: UUID | None = None,
    params: dict | None = None,
    word_budget: int | None = None,
    input_artifact_slugs: list[str] | None = None,
) -> TaskEnvelope:
    return TaskEnvelope(
        project_id=project_id or uuid4(),
        node_key=f"content.{capability}",
        agent="content",
        capability=capability,
        attempt=1,
        input_artifact_slugs=input_artifact_slugs or [],
        params=params or {},
        word_budget=word_budget,
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


def make_brief_payload() -> dict:
    return {
        "angle": "Async standups trade spontaneity for flexibility.",
        "audience_insight": "Managers want fewer meetings without losing alignment.",
        "key_points": [
            "Async standups eliminate timezone conflicts for distributed teams.",
            "They reduce meeting fatigue by removing the need for a live daily call.",
        ],
        "sources": [],
    }


def make_outline() -> Outline:
    return Outline(
        title="Async Standups Explained",
        sections=[
            OutlineSection(
                key="s1", title="Hook", summary="Async standups eliminate timezone conflicts.", weight=1.0
            ),
            OutlineSection(
                key="s2", title="Body", summary="They reduce meeting fatigue for distributed teams.", weight=2.0
            ),
        ],
    )


def make_bad_key_outline() -> Outline:
    """Section keys out of order -- must fail ContentAgent's structural check."""
    return Outline(
        title="Bad Outline",
        sections=[
            OutlineSection(key="s2", title="Hook", summary="Async standups cut timezone conflicts.", weight=1.0),
            OutlineSection(key="s1", title="Body", summary="They reduce meeting fatigue for teams.", weight=1.0),
        ],
    )


def make_script_draft(word_count: int) -> ScriptDraft:
    return ScriptDraft(text=" ".join(["word"] * word_count))


def make_scripts() -> list[Script]:
    return [
        Script(section_key="s1", text="Hook text about async standups and timezone conflicts."),
        Script(section_key="s2", text="Body text about meeting fatigue reduction for teams."),
    ]


def make_storyboard(cover_all: bool = True) -> Storyboard:
    # duration_s=3 for each -- must land within ±35% of narration_seconds(8,
    # "conversational")==3 (make_scripts()'s texts are both 8 words), since
    # ContentAgent._validate_storyboard now checks shot durations against
    # actual narration length, not just section coverage.
    shots = [
        StoryboardShot(section_key="s1", visual="laptops with chat windows open", overlay_text="Async", duration_s=3),
    ]
    if cover_all:
        shots.append(
            StoryboardShot(section_key="s2", visual="empty calendar, no meetings", overlay_text=None, duration_s=3)
        )
    return Storyboard(shots=shots)


# ---------------------------------------------------------------------------
# outline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outline_happy_path() -> None:
    envelope = make_envelope("outline")
    brief_artifact = make_artifact(
        envelope.project_id, "research.brief", "research_brief", "research-brief", make_brief_payload()
    )
    outline = make_outline()

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=brief_artifact),
        patch("app.agents.content.generate_structured", new_callable=AsyncMock, return_value=outline) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "content_outline"
    assert result.slug == "content-outline"
    assert result.summary == outline.title
    assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_outline_bad_key_order_triggers_repair() -> None:
    envelope = make_envelope("outline")
    brief_artifact = make_artifact(
        envelope.project_id, "research.brief", "research_brief", "research-brief", make_brief_payload()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=brief_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_bad_key_outline(), make_outline()],
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    assert mock_gen.await_args_list[0].kwargs["repair_hint"] is None
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "s1" in second_hint


@pytest.mark.asyncio
async def test_outline_wrong_section_count_triggers_repair() -> None:
    """Regression test for a real bug found via live testing: the outline
    prompt never told the model how many sections to produce, and nothing
    validated the count it chose against project.params["section_count"].
    director/template.py's expand_template always creates exactly
    section_count content.script.sN nodes -- an outline with more sections
    than that orphans the extras (never scripted/storyboarded) and dilutes
    every real section's word budget, since word_budget.allocate's weight
    pool is built from ALL outline sections. A real live run asked for 3
    sections and got 5, producing a video roughly a quarter of the
    requested length.
    """
    envelope = make_envelope("outline")
    brief_artifact = make_artifact(
        envelope.project_id, "research.brief", "research_brief", "research-brief", make_brief_payload()
    )
    # project.params["section_count"] is 2 (make_project()); this outline has 3.
    three_sections = Outline(
        title="Too Many Sections",
        sections=[
            OutlineSection(key="s1", title="Hook", summary="Async standups cut timezone conflicts.", weight=1.0),
            OutlineSection(key="s2", title="Body", summary="They reduce meeting fatigue for teams.", weight=1.0),
            OutlineSection(key="s3", title="Extra", summary="An orphaned third section.", weight=1.0),
        ],
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=brief_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            side_effect=[three_sections, make_outline()],
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "exactly 2 sections" in second_hint and "got 3" in second_hint


@pytest.mark.asyncio
async def test_outline_exhausts_retries() -> None:
    envelope = make_envelope("outline")
    brief_artifact = make_artifact(
        envelope.project_id, "research.brief", "research_brief", "research-brief", make_brief_payload()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=brief_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            return_value=make_bad_key_outline(),
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert mock_gen.await_count == ContentAgent.max_attempts


# ---------------------------------------------------------------------------
# script
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_script_happy_path() -> None:
    envelope = make_envelope("script", params={"section_key": "s2"}, word_budget=10)
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline().model_dump()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            return_value=make_script_draft(10),
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "content_script"
    assert result.slug == "content-script-s2"
    assert result.payload["section_key"] == "s2"
    assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_script_word_budget_violation_triggers_repair() -> None:
    envelope = make_envelope("script", params={"section_key": "s2"}, word_budget=10)
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline().model_dump()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_script_draft(3), make_script_draft(10)],
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "word" in second_hint.lower()


@pytest.mark.asyncio
async def test_script_exhausts_retries() -> None:
    envelope = make_envelope("script", params={"section_key": "s2"}, word_budget=10)
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline().model_dump()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            return_value=make_script_draft(3),
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is False
    assert mock_gen.await_count == ContentAgent.max_attempts


@pytest.mark.asyncio
async def test_script_missing_section_key_raises() -> None:
    """A section_key with no match in the outline should fail fast, not silently proceed."""
    envelope = make_envelope("script", params={"section_key": "s99"}, word_budget=10)
    outline_artifact = make_artifact(
        envelope.project_id, "content.outline", "content_outline", "content-outline", make_outline().model_dump()
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.content.get_artifact_by_slug", new_callable=AsyncMock, return_value=outline_artifact),
    ):
        with pytest.raises(ValueError, match="s99"):
            await ContentAgent().run(envelope)


# ---------------------------------------------------------------------------
# storyboard
# ---------------------------------------------------------------------------


def _artifact_lookup_side_effect(artifacts_by_slug: dict[str, Artifact]):
    def _pick(project_id: UUID, slug: str) -> Artifact:
        return artifacts_by_slug[slug]

    return _pick


@pytest.mark.asyncio
async def test_storyboard_happy_path() -> None:
    envelope = make_envelope("storyboard", input_artifact_slugs=["content-script-s1", "content-script-s2"])
    scripts = make_scripts()
    artifacts_by_slug = {
        "content-script-s1": make_artifact(
            envelope.project_id, "content.script.s1", "content_script", "content-script-s1", scripts[0].model_dump()
        ),
        "content-script-s2": make_artifact(
            envelope.project_id, "content.script.s2", "content_script", "content-script-s2", scripts[1].model_dump()
        ),
    }

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch(
            "app.agents.content.get_artifact_by_slug",
            new_callable=AsyncMock,
            side_effect=_artifact_lookup_side_effect(artifacts_by_slug),
        ),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            return_value=make_storyboard(cover_all=True),
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "content_storyboard"
    assert result.slug == "content-storyboard"
    assert result.summary == "2 shots"
    assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_storyboard_missing_coverage_triggers_repair() -> None:
    envelope = make_envelope("storyboard", input_artifact_slugs=["content-script-s1", "content-script-s2"])
    scripts = make_scripts()
    artifacts_by_slug = {
        "content-script-s1": make_artifact(
            envelope.project_id, "content.script.s1", "content_script", "content-script-s1", scripts[0].model_dump()
        ),
        "content-script-s2": make_artifact(
            envelope.project_id, "content.script.s2", "content_script", "content-script-s2", scripts[1].model_dump()
        ),
    }

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch(
            "app.agents.content.get_artifact_by_slug",
            new_callable=AsyncMock,
            side_effect=_artifact_lookup_side_effect(artifacts_by_slug),
        ),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_storyboard(cover_all=False), make_storyboard(cover_all=True)],
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None and "s2" in second_hint


@pytest.mark.asyncio
async def test_storyboard_undertimed_shots_triggers_repair() -> None:
    """Regression test for a real bug found via live testing: covering every
    section with at least one shot (the only thing previously validated)
    doesn't stop shot durations from being wildly disconnected from how
    long the section's script actually takes to read aloud. A live run
    generated a 573-word section (~229s of narration) with shots totaling
    just 44s -- a real finished video came out roughly a fifth of its
    intended length despite the script itself being correctly sized.
    """
    envelope = make_envelope("storyboard", input_artifact_slugs=["content-script-s1", "content-script-s2"])
    # ~200 words each -> narration_seconds(200, "conversational") == 80s
    long_scripts = [
        Script(section_key="s1", text=" ".join(["word"] * 200)),
        Script(section_key="s2", text=" ".join(["word"] * 200)),
    ]
    artifacts_by_slug = {
        "content-script-s1": make_artifact(
            envelope.project_id, "content.script.s1", "content_script", "content-script-s1", long_scripts[0].model_dump()
        ),
        "content-script-s2": make_artifact(
            envelope.project_id, "content.script.s2", "content_script", "content-script-s2", long_scripts[1].model_dump()
        ),
    }
    # Covers both sections (passes the old check) but with only ~8s of
    # shots against an ~80s narration target -- must still fail.
    undertimed = Storyboard(
        shots=[
            StoryboardShot(section_key="s1", visual="a", overlay_text=None, duration_s=4),
            StoryboardShot(section_key="s2", visual="b", overlay_text=None, duration_s=4),
        ]
    )
    well_timed = Storyboard(
        shots=[
            StoryboardShot(section_key="s1", visual="a", overlay_text=None, duration_s=80),
            StoryboardShot(section_key="s2", visual="b", overlay_text=None, duration_s=80),
        ]
    )

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch(
            "app.agents.content.get_artifact_by_slug",
            new_callable=AsyncMock,
            side_effect=_artifact_lookup_side_effect(artifacts_by_slug),
        ),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            side_effect=[undertimed, well_timed],
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is True
    assert mock_gen.await_count == 2
    second_hint = mock_gen.await_args_list[1].kwargs["repair_hint"]
    assert second_hint is not None
    assert "s1" in second_hint and "s2" in second_hint


@pytest.mark.asyncio
async def test_storyboard_exhausts_retries() -> None:
    envelope = make_envelope("storyboard", input_artifact_slugs=["content-script-s1", "content-script-s2"])
    scripts = make_scripts()
    artifacts_by_slug = {
        "content-script-s1": make_artifact(
            envelope.project_id, "content.script.s1", "content_script", "content-script-s1", scripts[0].model_dump()
        ),
        "content-script-s2": make_artifact(
            envelope.project_id, "content.script.s2", "content_script", "content-script-s2", scripts[1].model_dump()
        ),
    }

    with (
        patch("app.agents.content.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch(
            "app.agents.content.get_artifact_by_slug",
            new_callable=AsyncMock,
            side_effect=_artifact_lookup_side_effect(artifacts_by_slug),
        ),
        patch(
            "app.agents.content.generate_structured",
            new_callable=AsyncMock,
            return_value=make_storyboard(cover_all=False),
        ) as mock_gen,
    ):
        result = await ContentAgent().run(envelope)

    assert result.ok is False
    assert mock_gen.await_count == ContentAgent.max_attempts


# ---------------------------------------------------------------------------
# _section_word_budget (pure function, no mocking needed)
# ---------------------------------------------------------------------------


def test_section_word_budget_folds_hook_and_outro() -> None:
    outline = Outline(
        title="Test",
        sections=[
            OutlineSection(key="s1", title="Hook", summary="grab attention", weight=1.0),
            OutlineSection(key="s2", title="Body", summary="main point", weight=2.0),
            OutlineSection(key="s3", title="Outro", summary="wrap up", weight=1.0),
        ],
    )
    params = {"total_seconds": 180, "tone": "conversational"}

    # 180s @ 150 wpm = 450 words; hook 8% (36) + outro 6% (27) reserved;
    # remaining 387 body words split 1:2:1 across s1/s2/s3 -> 97/194/97,
    # with hook folded into s1 and outro folded into s3.
    assert _section_word_budget(outline, "s1", params) == 133
    assert _section_word_budget(outline, "s2", params) == 194
    assert _section_word_budget(outline, "s3", params) == 124
