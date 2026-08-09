"""Unit tests for ResearchAgent's control flow.

These mock the three I/O boundaries (project fetch, Tavily search, LLM
generation) so the suite runs offline/free and exercises BaseAgent.run's
generate -> validate -> repair loop against the real (unmocked)
validators/claims.py grounding check.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.research import ResearchAgent, ResearchBrief, Source
from app.llm.search import SearchResult
from app.models import Project, ProjectStatus, TaskEnvelope

NOW = datetime.now(timezone.utc)


def make_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        project_id=uuid4(),
        node_key="research.brief",
        agent="research",
        capability="brief",
        attempt=1,
    )


def make_project() -> Project:
    return Project(
        id=uuid4(),
        title="Async standups",
        idea="Why fully-async daily standups quietly kill remote team morale.",
        status=ProjectStatus.PLANNING,
        params={"audience": "engineering managers", "tone": "conversational"},
        created_at=NOW,
        updated_at=NOW,
    )


def make_sources() -> list[SearchResult]:
    return [
        SearchResult(
            title="Async Standups Guide",
            url="https://example.com/async",
            content="Async standups eliminate timezone conflicts and reduce meeting fatigue for remote teams.",
        )
    ]


def make_grounded_brief() -> ResearchBrief:
    """A brief whose key_points are lexically grounded in make_sources()."""
    return ResearchBrief(
        angle="Async standups trade spontaneity for flexibility.",
        audience_insight="Managers want fewer meetings without losing alignment.",
        key_points=[
            "Async standups eliminate timezone conflicts for distributed teams.",
            "They reduce meeting fatigue by removing the need for a live daily call.",
            "Teams still need a consistent schedule to keep async updates useful.",
        ],
        sources=[
            Source(
                title="Async Standups Guide",
                url="https://example.com/async",
                excerpt="Async standups eliminate timezone conflicts and reduce meeting fatigue for remote teams.",
            )
        ],
    )


def make_ungrounded_brief() -> ResearchBrief:
    """A brief with one key_point that shares no vocabulary with any source."""
    grounded = make_grounded_brief()
    return grounded.model_copy(
        update={
            "key_points": grounded.key_points
            + ["Quantum computing breakthroughs enabled fully autonomous spacecraft navigation systems."]
        }
    )


@pytest.mark.asyncio
async def test_successful_run_returns_agent_result() -> None:
    envelope = make_envelope()

    with (
        patch("app.agents.research.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.research.tavily_search", new_callable=AsyncMock, return_value=make_sources()),
        patch(
            "app.agents.research.generate_structured",
            new_callable=AsyncMock,
            return_value=make_grounded_brief(),
        ) as mock_generate,
    ):
        result = await ResearchAgent().run(envelope)

    assert result.ok is True
    assert result.artifact_type == "research_brief"
    assert result.slug == "research-brief"
    assert result.summary == make_grounded_brief().angle
    assert mock_generate.await_count == 1


@pytest.mark.asyncio
async def test_reference_material_grounds_product_specific_claims() -> None:
    """Regression test for a real gap: check_grounding only ever matched
    claims against Tavily's web search results, so there was no way to
    write about a proprietary/unreleased feature a web search can't find --
    the LLM is explicitly told not to invent facts absent from the sources,
    so it had no legitimate way to say anything specific about it. A key
    point traceable ONLY to project.params["reference_material"] (nothing
    in the mocked web search shares its vocabulary) must still pass
    grounding once that param is set.
    """
    envelope = make_envelope()
    project = make_project()
    project = project.model_copy(
        update={
            "params": {
                **project.params,
                "reference_material": "Smart Filters lets users save filter presets combining tags, "
                "dates, and assignees to instantly narrow down large task lists.",
            }
        }
    )
    brief_grounded_in_reference_material = ResearchBrief(
        angle="Smart Filters turns manual scrolling into one click.",
        audience_insight="Users with large task lists want instant results, not more scrolling.",
        key_points=[
            "Smart Filters lets users save filter presets combining tags, dates, and assignees.",
            "Saved presets instantly narrow down large task lists without manual scrolling.",
            "Teams still need a consistent schedule to keep their workflow useful.",
        ],
        sources=[
            Source(
                title="Product/feature details you provided",
                url="user-provided",
                excerpt="Smart Filters lets users save filter presets combining tags, dates, and assignees "
                "to instantly narrow down large task lists without manual scrolling workflow.",
            )
        ],
    )

    with (
        patch("app.agents.research.get_project", new_callable=AsyncMock, return_value=project),
        patch("app.agents.research.tavily_search", new_callable=AsyncMock, return_value=make_sources()),
        patch(
            "app.agents.research.generate_structured",
            new_callable=AsyncMock,
            return_value=brief_grounded_in_reference_material,
        ) as mock_generate,
    ):
        result = await ResearchAgent().run(envelope)

    assert result.ok is True
    assert mock_generate.await_count == 1
    # The prompt actually sent to the LLM must have carried the reference
    # material through, not just the web search results.
    prompt_sent = mock_generate.await_args.args[0]
    assert "Smart Filters" in prompt_sent
    assert "Product/feature details you provided" in prompt_sent


@pytest.mark.asyncio
async def test_ungrounded_draft_triggers_repair_retry() -> None:
    envelope = make_envelope()

    with (
        patch("app.agents.research.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.research.tavily_search", new_callable=AsyncMock, return_value=make_sources()),
        patch(
            "app.agents.research.generate_structured",
            new_callable=AsyncMock,
            side_effect=[make_ungrounded_brief(), make_grounded_brief()],
        ) as mock_generate,
    ):
        result = await ResearchAgent().run(envelope)

    assert result.ok is True
    assert mock_generate.await_count == 2

    # the retry must have been told what was wrong with attempt 1
    first_call_hint = mock_generate.await_args_list[0].kwargs["repair_hint"]
    second_call_hint = mock_generate.await_args_list[1].kwargs["repair_hint"]
    assert first_call_hint is None
    assert second_call_hint is not None
    assert "spacecraft" in second_call_hint or "not traceable" in second_call_hint


@pytest.mark.asyncio
async def test_exhausts_retries_returns_failure() -> None:
    envelope = make_envelope()

    with (
        patch("app.agents.research.get_project", new_callable=AsyncMock, return_value=make_project()),
        patch("app.agents.research.tavily_search", new_callable=AsyncMock, return_value=make_sources()),
        patch(
            "app.agents.research.generate_structured",
            new_callable=AsyncMock,
            return_value=make_ungrounded_brief(),
        ) as mock_generate,
    ):
        result = await ResearchAgent().run(envelope)

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert result.error_message
    assert mock_generate.await_count == ResearchAgent.max_attempts
