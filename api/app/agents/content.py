"""Content agent: produces `content.outline`, `content.script.sN`, `content.storyboard`.

One class, three capabilities, dispatched on `env.capability` inside each of
the four BaseAgent hooks. Outline sections map 1:1 onto content.script.sN
node keys ("s1".."sN") -- there are no separate hook/outro nodes, so the
hook/outro word-budget carve-outs from validators/word_budget.allocate fold
into the first and last section's targets instead.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, BaseAgent
from app.director.template import DEFAULT_SECTION_COUNT
from app.llm.client import GEMINI_MODEL
from app.llm.structured import generate_structured
from app.models import AgentResult, TaskEnvelope, ValidationReport
from app.services.artifacts import get_artifact_by_slug
from app.services.projects import get_project
from app.validators.claims import check_grounding, extract_claims
from app.validators.word_budget import allocate, narration_seconds
from app.validators.word_budget import check as check_word_budget
from app.validators.word_budget import check_shot_durations

# ---------------------------------------------------------------------------
# Schemas -- one per artifact this agent produces/consumes.
# ---------------------------------------------------------------------------


class OutlineSection(BaseModel):
    key: str  # "s1".."sN" -- matches a content.script.<key> node 1:1, in order
    title: str
    summary: str
    weight: float = 1.0  # relative share of runtime/words, fed to word_budget.allocate


class Outline(BaseModel):
    title: str
    sections: list[OutlineSection] = Field(min_length=2, max_length=8)


class ScriptDraft(BaseModel):
    """What the LLM produces for one section -- just the narration text.

    section_key isn't part of the LLM's output; build_output stamps it on
    from ctx.envelope.params so it can't come back mismatched.
    """

    text: str


class Script(BaseModel):
    """What gets persisted as the content_script artifact for one section."""

    section_key: str
    text: str


class StoryboardShot(BaseModel):
    section_key: str
    visual: str
    overlay_text: str | None = None
    duration_s: int


class Storyboard(BaseModel):
    shots: list[StoryboardShot] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_OUTLINE_PROMPT = """You are structuring a piece of content from a research brief.

Angle: {angle}
Audience insight: {audience_insight}
Key points:
{key_points_block}

Break this into a script outline of EXACTLY {section_count} sections with
keys "s1", "s2", ... "s{section_count}" in order -- not more, not fewer. The
first section functions as the hook (grab attention fast); the last section
functions as the outro (wrap up / call to action). Each section needs a
title, a one-to-two sentence summary grounded in the key points above, and a
`weight` (relative share of runtime -- any positive number, does not need to
sum to 1).
"""

_SCRIPT_PROMPT = """You are writing the spoken script for one section of a video.

Video title: {title}
Section: {section_title} ({section_key} of {total_sections})
What this section covers: {section_summary}
{position_note}
Tone: {tone}
Target length: approximately {word_budget} words

Write ONLY the spoken narration text for this section -- no stage directions,
no section headers, no timestamps.
"""

_STORYBOARD_PROMPT = """You are storyboarding a video from its finished script.

Video title: {title}

Script, by section -- each labeled with how long it takes to read aloud:
{script_block}

For each section, produce one or more shots: a visual description, optional
on-screen overlay text (4 words or fewer), and an estimated duration in
seconds. Cover every section key listed above at least once. Critically,
each section's shots must SUM to approximately that section's stated
narration time -- do not compress the pacing into a couple of quick shots;
a longer section needs correspondingly more shots or longer ones, not a
short summary of it.
"""


class ContentAgent(BaseAgent):
    agent_name = "content"

    # capabilities: outline, script, storyboard

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        ctx = AgentContext(envelope=env)
        project = await get_project(env.project_id)
        ctx.input_artifacts["project"] = project

        if env.capability == "outline":
            brief_artifact = await get_artifact_by_slug(env.project_id, "research-brief")
            ctx.input_artifacts["brief"] = brief_artifact.payload

        elif env.capability == "script":
            outline_artifact = await get_artifact_by_slug(env.project_id, "content-outline")
            outline = Outline.model_validate(outline_artifact.payload)
            section_key = env.params["section_key"]
            section = next((s for s in outline.sections if s.key == section_key), None)
            if section is None:
                raise ValueError(f"outline has no section with key {section_key!r}")

            ctx.input_artifacts["outline"] = outline
            ctx.input_artifacts["section"] = section
            ctx.input_artifacts["word_budget"] = env.word_budget or _section_word_budget(
                outline, section_key, project.params
            )

        elif env.capability == "storyboard":
            scripts = [
                Script.model_validate((await get_artifact_by_slug(env.project_id, slug)).payload)
                for slug in env.input_artifact_slugs
            ]
            ctx.input_artifacts["scripts"] = scripts

        else:
            raise ValueError(f"unknown content capability: {env.capability!r}")

        return ctx

    async def generate(self, ctx: AgentContext) -> Any:
        capability = ctx.envelope.capability
        if capability == "outline":
            return await self._generate_outline(ctx)
        if capability == "script":
            return await self._generate_script(ctx)
        if capability == "storyboard":
            return await self._generate_storyboard(ctx)
        raise ValueError(f"unknown content capability: {capability!r}")

    async def _generate_outline(self, ctx: AgentContext) -> Outline:
        project = ctx.input_artifacts["project"]
        brief = ctx.input_artifacts["brief"]
        key_points_block = "\n".join(f"- {point}" for point in brief.get("key_points", []))
        section_count = project.params.get("section_count", DEFAULT_SECTION_COUNT)
        prompt = _OUTLINE_PROMPT.format(
            angle=brief.get("angle", ""),
            audience_insight=brief.get("audience_insight", ""),
            key_points_block=key_points_block,
            section_count=section_count,
        )
        return await generate_structured(prompt, schema=Outline, repair_hint=ctx.repair_hint)

    async def _generate_script(self, ctx: AgentContext) -> ScriptDraft:
        project = ctx.input_artifacts["project"]
        outline: Outline = ctx.input_artifacts["outline"]
        section: OutlineSection = ctx.input_artifacts["section"]
        word_budget: int = ctx.input_artifacts["word_budget"]

        is_hook = section.key == outline.sections[0].key
        is_outro = section.key == outline.sections[-1].key
        position_note = (
            "This is the opening section -- open with a hook."
            if is_hook
            else "This is the closing section -- wrap up with an outro/call to action."
            if is_outro
            else ""
        )

        prompt = _SCRIPT_PROMPT.format(
            title=outline.title,
            section_title=section.title,
            section_key=section.key,
            total_sections=len(outline.sections),
            section_summary=section.summary,
            position_note=position_note,
            tone=project.params.get("tone", "conversational"),
            word_budget=word_budget,
        )
        return await generate_structured(prompt, schema=ScriptDraft, repair_hint=ctx.repair_hint)

    async def _generate_storyboard(self, ctx: AgentContext) -> Storyboard:
        project = ctx.input_artifacts["project"]
        scripts: list[Script] = ctx.input_artifacts["scripts"]
        tone = project.params.get("tone", "conversational")
        script_block = "\n\n".join(
            f"[{script.section_key}] (~{narration_seconds(len(script.text.split()), tone)}s to read aloud)\n{script.text}"
            for script in scripts
        )
        prompt = _STORYBOARD_PROMPT.format(title=project.title, script_block=script_block)
        return await generate_structured(prompt, schema=Storyboard, repair_hint=ctx.repair_hint)

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        capability = ctx.envelope.capability
        if capability == "outline":
            return self._validate_outline(ctx, generated)
        if capability == "script":
            return self._validate_script(ctx, generated)
        if capability == "storyboard":
            return self._validate_storyboard(ctx, generated)
        raise ValueError(f"unknown content capability: {capability!r}")

    def _validate_outline(self, ctx: AgentContext, outline: Outline) -> ValidationReport:
        # Real bug found via live testing: this only ever checked that keys
        # were sequential given however many sections the model produced --
        # nothing checked that count against project.params["section_count"]
        # at all. The Director's template always creates exactly
        # section_count content.script.sN nodes (director/template.py's
        # expand_template), so an outline with more sections than that
        # orphans the extras (no script/storyboard ever covers them) and,
        # worse, still counts their `weight` in word_budget.allocate's pool
        # -- silently shrinking every real section's word budget, and
        # misdirecting the outro carve-out onto a phantom last section
        # instead of the true final scripted one.
        project = ctx.input_artifacts["project"]
        expected_count = project.params.get("section_count", DEFAULT_SECTION_COUNT)
        if len(outline.sections) != expected_count:
            hint = f"Outline must have exactly {expected_count} sections, got {len(outline.sections)}."
            return ValidationReport(ok=False, failures=[hint], repair_hint=hint)

        expected_keys = [f"s{i}" for i in range(1, len(outline.sections) + 1)]
        actual_keys = [section.key for section in outline.sections]
        if actual_keys != expected_keys:
            hint = f"Section keys must be {expected_keys} in order, got {actual_keys}."
            return ValidationReport(ok=False, failures=[hint], repair_hint=hint)

        brief = ctx.input_artifacts["brief"]
        sources = [brief.get("angle", ""), *brief.get("key_points", [])]
        claims = extract_claims(" ".join(section.summary for section in outline.sections))
        return check_grounding(claims, sources)

    def _validate_script(self, ctx: AgentContext, draft: ScriptDraft) -> ValidationReport:
        word_budget: int = ctx.input_artifacts["word_budget"]
        return check_word_budget(draft.text, word_budget)

    def _validate_storyboard(self, ctx: AgentContext, storyboard: Storyboard) -> ValidationReport:
        scripts: list[Script] = ctx.input_artifacts["scripts"]
        expected_keys = {script.section_key for script in scripts}
        covered_keys = {shot.section_key for shot in storyboard.shots}
        missing = sorted(expected_keys - covered_keys)
        if missing:
            hint = f"Add at least one shot for each of these sections: {', '.join(missing)}."
            return ValidationReport(
                ok=False,
                failures=[f"no shot covers section(s): {', '.join(missing)}"],
                repair_hint=hint,
            )

        # Real bug found via live testing: coverage alone doesn't stop shot
        # durations from being completely disconnected from how long the
        # section's script actually takes to read aloud -- a 573-word
        # section (~229s of narration) got assigned just 44s of shots,
        # producing a finished video roughly a fifth of its intended length
        # despite the script itself being correctly sized by then.
        project = ctx.input_artifacts["project"]
        tone = project.params.get("tone", "conversational")
        expected_by_section = {
            script.section_key: narration_seconds(len(script.text.split()), tone) for script in scripts
        }
        actual_by_section: dict[str, int] = {}
        for shot in storyboard.shots:
            actual_by_section[shot.section_key] = actual_by_section.get(shot.section_key, 0) + shot.duration_s

        return check_shot_durations(actual_by_section, expected_by_section)

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        capability = ctx.envelope.capability
        if capability == "outline":
            return self._build_outline_output(generated)
        if capability == "script":
            return self._build_script_output(ctx, generated)
        if capability == "storyboard":
            return self._build_storyboard_output(generated)
        raise ValueError(f"unknown content capability: {capability!r}")

    def _build_outline_output(self, outline: Outline) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="content_outline",
            slug="content-outline",
            payload=outline.model_dump(),
            summary=outline.title,
            model=GEMINI_MODEL,
        )

    def _build_script_output(self, ctx: AgentContext, draft: ScriptDraft) -> AgentResult:
        section_key = ctx.envelope.params["section_key"]
        script = Script(section_key=section_key, text=draft.text)
        return AgentResult(
            ok=True,
            artifact_type="content_script",
            slug=f"content-script-{section_key}",
            payload=script.model_dump(),
            summary=draft.text[:120],
            model=GEMINI_MODEL,
        )

    def _build_storyboard_output(self, storyboard: Storyboard) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="content_storyboard",
            slug="content-storyboard",
            payload=storyboard.model_dump(),
            summary=f"{len(storyboard.shots)} shots",
            model=GEMINI_MODEL,
        )


def _section_word_budget(outline: Outline, section_key: str, project_params: dict[str, Any]) -> int:
    """Best-effort word budget when the Director hasn't precomputed one on the
    envelope yet -- lets `script` be exercised standalone. Folds the hook
    carve-out into the first section and the outro carve-out into the last,
    since there's no dedicated hook/outro node to spend them on.
    """
    # 360s (6min) default -- the frontend's create-project form now sends
    # total_seconds explicitly (a "video length" field), so this fallback
    # only matters when script is exercised standalone (tests, direct API
    # calls) without it. Previously defaulted to 180s (3min) with no way for
    # a user to change it at all -- every project was a 3-minute video
    # regardless of section_count.
    total_seconds = project_params.get("total_seconds", 360)
    tone = project_params.get("tone", "conversational")
    weights = {section.key: section.weight for section in outline.sections}
    allocation = allocate(total_seconds, weights, tone)

    budget = allocation[section_key]
    if section_key == outline.sections[0].key:
        budget += allocation["hook"]
    if section_key == outline.sections[-1].key:
        budget += allocation["outro"]
    return budget
