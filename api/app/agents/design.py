"""Design agent: produces `design.visual_language`, `design.thumbnails`.

Same shape as ContentAgent: one class, two capabilities, dispatched on
env.capability inside each BaseAgent hook. content-outline (a cross-agent
artifact from ContentAgent) is read as a raw dict, same as ResearchAgent's
brief is in content.py -- only an agent's own prior-capability artifacts get
re-validated into a typed schema (design-visual-language here).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, BaseAgent
from app.llm.client import GEMINI_MODEL
from app.llm.structured import generate_structured
from app.models import AgentResult, TaskEnvelope, ValidationReport
from app.services.artifacts import get_artifact_by_slug
from app.services.projects import get_project
from app.validators.design_rules import check_contrast, check_overlay_word_count

_HEX_PATTERN = r"^#[0-9A-Fa-f]{6}$"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ColorSwatch(BaseModel):
    role: str  # "background" | "text" | "accent" | "highlight" ...
    name: str
    hex: str = Field(pattern=_HEX_PATTERN)


class VisualLanguage(BaseModel):
    mood: str
    palette: list[ColorSwatch] = Field(min_length=3, max_length=6)
    typography: str
    imagery_style: str
    avoid: list[str] = Field(default_factory=list)


class ThumbnailConcept(BaseModel):
    concept_name: str
    visual: str
    overlay_text: str
    text_color_hex: str = Field(pattern=_HEX_PATTERN)
    background_color_hex: str = Field(pattern=_HEX_PATTERN)


class ThumbnailSet(BaseModel):
    concepts: list[ThumbnailConcept] = Field(min_length=2, max_length=4)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_VISUAL_LANGUAGE_PROMPT = """You are defining the visual style guide for a piece of content, based on its outline.

Title: {title}
Sections:
{sections_block}

Tone: {tone}

Propose a visual language: an overall mood in one sentence, a color palette
of 3-6 swatches (each with a `role` -- at minimum one "background" role and
one "text" role, plus optional "accent"/"highlight" roles -- a short `name`,
and a `hex` code like "#1A2B3C"), a one-sentence typography style
description, a one-sentence imagery/photography style description, and an
optional list of things to avoid.

The "text" swatch must be clearly readable against the "background" swatch.
"""

_THUMBNAILS_PROMPT = """You are designing thumbnail concepts using an established visual language.

Content title: {title}
Content idea: {idea}
Visual language mood: {mood}
Typography: {typography}
Imagery style: {imagery_style}
Palette:
{palette_block}

Propose 2-4 distinct thumbnail concepts. Each needs a concept_name, a visual
description of the composition/imagery, bold overlay_text (4 words or
fewer), a text_color_hex for the overlay text, and a background_color_hex
for what sits directly behind it. Colors should be drawn from or consistent
with the palette above, and the text/background pair must be high-contrast
and readable at a glance.
"""


class DesignAgent(BaseAgent):
    agent_name = "design"

    # capabilities: visual_language, thumbnails

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        ctx = AgentContext(envelope=env)
        project = await get_project(env.project_id)
        ctx.input_artifacts["project"] = project

        if env.capability == "visual_language":
            outline_artifact = await get_artifact_by_slug(env.project_id, "content-outline")
            ctx.input_artifacts["outline"] = outline_artifact.payload

        elif env.capability == "thumbnails":
            vl_artifact = await get_artifact_by_slug(env.project_id, "design-visual-language")
            ctx.input_artifacts["visual_language"] = VisualLanguage.model_validate(vl_artifact.payload)

        else:
            raise ValueError(f"unknown design capability: {env.capability!r}")

        return ctx

    async def generate(self, ctx: AgentContext) -> Any:
        capability = ctx.envelope.capability
        if capability == "visual_language":
            return await self._generate_visual_language(ctx)
        if capability == "thumbnails":
            return await self._generate_thumbnails(ctx)
        raise ValueError(f"unknown design capability: {capability!r}")

    async def _generate_visual_language(self, ctx: AgentContext) -> VisualLanguage:
        project = ctx.input_artifacts["project"]
        outline: dict[str, Any] = ctx.input_artifacts["outline"]
        sections_block = "\n".join(
            f"- {section.get('title', '')}: {section.get('summary', '')}"
            for section in outline.get("sections", [])
        )
        prompt = _VISUAL_LANGUAGE_PROMPT.format(
            title=outline.get("title", project.title),
            sections_block=sections_block,
            tone=project.params.get("tone", "conversational"),
        )
        return await generate_structured(prompt, schema=VisualLanguage, repair_hint=ctx.repair_hint)

    async def _generate_thumbnails(self, ctx: AgentContext) -> ThumbnailSet:
        project = ctx.input_artifacts["project"]
        vl: VisualLanguage = ctx.input_artifacts["visual_language"]
        palette_block = "\n".join(f"- {swatch.role}: {swatch.name} ({swatch.hex})" for swatch in vl.palette)
        prompt = _THUMBNAILS_PROMPT.format(
            title=project.title,
            idea=project.idea,
            mood=vl.mood,
            typography=vl.typography,
            imagery_style=vl.imagery_style,
            palette_block=palette_block,
        )
        return await generate_structured(prompt, schema=ThumbnailSet, repair_hint=ctx.repair_hint)

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        capability = ctx.envelope.capability
        if capability == "visual_language":
            return self._validate_visual_language(generated)
        if capability == "thumbnails":
            return self._validate_thumbnails(generated)
        raise ValueError(f"unknown design capability: {capability!r}")

    def _validate_visual_language(self, vl: VisualLanguage) -> ValidationReport:
        swatches_by_role = {swatch.role: swatch for swatch in vl.palette}
        missing = [role for role in ("background", "text") if role not in swatches_by_role]
        if missing:
            hint = f"Palette must include swatches with role={missing}."
            return ValidationReport(ok=False, failures=[hint], repair_hint=hint)

        return check_contrast(swatches_by_role["text"].hex, swatches_by_role["background"].hex)

    def _validate_thumbnails(self, thumbnails: ThumbnailSet) -> ValidationReport:
        failures: list[str] = []
        hints: list[str] = []
        for concept in thumbnails.concepts:
            for report in (
                check_overlay_word_count(concept.overlay_text),
                check_contrast(concept.text_color_hex, concept.background_color_hex),
            ):
                if not report.ok:
                    failures.append(f"{concept.concept_name}: {report.failures[0]}")
                    if report.repair_hint:
                        hints.append(report.repair_hint)

        if not failures:
            return ValidationReport(ok=True)
        return ValidationReport(ok=False, failures=failures, repair_hint=" | ".join(hints))

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        capability = ctx.envelope.capability
        if capability == "visual_language":
            return self._build_visual_language_output(generated)
        if capability == "thumbnails":
            return self._build_thumbnails_output(generated)
        raise ValueError(f"unknown design capability: {capability!r}")

    def _build_visual_language_output(self, vl: VisualLanguage) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="design_visual_language",
            slug="design-visual-language",
            payload=vl.model_dump(),
            summary=vl.mood,
            model=GEMINI_MODEL,
        )

    def _build_thumbnails_output(self, thumbnails: ThumbnailSet) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="design_thumbnails",
            slug="design-thumbnails",
            payload=thumbnails.model_dump(),
            summary=f"{len(thumbnails.concepts)} thumbnail concepts",
            model=GEMINI_MODEL,
        )
