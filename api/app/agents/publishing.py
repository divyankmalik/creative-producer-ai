"""Publishing agent: produces `publishing.seo`, `publishing.package`.

BLUEPRINT ONLY -- schemas are real (contracts), method bodies are TODO.
Same shape as ResearchAgent/ContentAgent/DesignAgent: one class, capabilities
dispatched off env.capability inside each BaseAgent hook.

Dependency edges (from director/template.py):
    publishing.seo     <- content.outline (HARD), design.thumbnails (SOFT)
    publishing.package <- content.storyboard (HARD), publishing.seo (HARD)

The one genuinely new problem this agent has to solve that Research/Content/
Design didn't: `publishing.seo` has a SOFT dependency on `design.thumbnails`.
Hard dependencies you've been able to assume are always there by the time
this node runs (the Director wouldn't have scheduled it otherwise). A soft
dependency might legitimately not exist yet, or exist but be stale -- and
that must NOT be a hard failure. `get_artifact_by_slug` currently raises
(via supabase's `.single()`) when no row matches, which is correct behavior
for a hard dependency but wrong for a soft one. Before build_context can
fetch design-thumbnails safely you need a way to ask "does this exist?"
without an exception as the normal-case control flow. Two ways to solve it,
pick one:
  (a) wrap the get_artifact_by_slug call in build_context in a try/except
      and treat "not found" as thumbnails=None
  (b) add a new services/artifacts.try_get_artifact_by_slug(project_id, slug)
      -> Artifact | None that swallows the not-found case once, so every
      future soft-dependency lookup (there will be more agents later) reuses
      it instead of each agent re-implementing its own try/except
(b) is the more reusable fix; (a) is faster to write for just this one case.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from app.services.projects import get_project

from app.agents.base import AgentContext, BaseAgent
from app.models import Artifact, AgentResult, TaskEnvelope, ValidationReport

from app.services.artifacts import get_artifact_by_slug, try_get_artifact_by_slug
from app.agents.content import Outline, Storyboard, Script  # only if you need Script too
from app.llm.structured import generate_structured
from app.llm.client import GEMINI_MODEL

# ---------------------------------------------------------------------------
# Validation bounds -- what search engines/platforms actually display before
# truncating, not arbitrary preferences. Same category as
# validators/word_budget.py's WPM constants.
# ---------------------------------------------------------------------------

MAX_SEO_TITLE_CHARS = 60
MIN_SEO_DESCRIPTION_CHARS = 50
MAX_SEO_DESCRIPTION_CHARS = 160

# ---------------------------------------------------------------------------
# Schemas -- these are real contracts, not logic. Adjust freely, but they're
# a reasonable starting point consistent with Outline/VisualLanguage's style.
# ---------------------------------------------------------------------------


class SeoMetadata(BaseModel):
    """What the LLM produces for `publishing.seo`."""

    seo_title: str  # aim ~60 chars -- validate() should enforce a real bound, not just "aim"
    seo_description: str  # aim ~155 chars
    tags: list[str] = Field(min_length=3, max_length=15)
    # Only meaningful when design.thumbnails was actually available in build_context;
    # None is the expected value when the soft dependency was missing, not an error.
    thumbnail_alignment_note: str | None = None


class PackageSection(BaseModel):
    """One storyboard shot carried into the final package, unchanged --
    package doesn't regenerate content, it assembles what already exists.
    """

    section_key: str
    visual: str
    overlay_text: str | None = None
    duration_s: int


class PublishingPackage(BaseModel):
    """What gets persisted as the content_storyboard... err, publishing_package
    artifact: the storyboard + seo metadata merged into one deliverable.

    NOTE: this is mostly an assembly step, not a generation step -- see the
    generate() blueprint below for why that changes this capability's shape
    compared to every other capability you've built so far.
    """

    title: str
    seo_title: str
    seo_description: str
    tags: list[str]
    sections: list[PackageSection]


# ---------------------------------------------------------------------------
# Prompts -- only `seo` needs one; `package` is assembly, not generation
# (see generate() blueprint below).
# ---------------------------------------------------------------------------

_SEO_PROMPT = """You are writing SEO metadata for a piece of content.

Title: {title}
Sections:
{sections_block}
{thumbnail_block}

Write an seo_title (aim for ~60 characters), an seo_description (aim for
~155 characters), and 3-15 tags. {thumbnail_instruction}
"""


class PublishingAgent(BaseAgent):
    agent_name = "publishing"

    # capabilities: seo, package

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        ctx = AgentContext(envelope=env)                                        # empty working state for this run
        project = await get_project(env.project_id)                             # every capability needs title/tone
        ctx.input_artifacts["project"] = project                                # stash it for generate() to read

        if env.capability == "seo":
            outline_artifact = await get_artifact_by_slug(env.project_id, "content-outline")  # HARD dep -> raises if missing (correct: Director wouldn't schedule seo otherwise)
            ctx.input_artifacts["outline"] = outline_artifact.payload           # kept as raw dict, not typed

            # SOFT dependency: missing/never-generated thumbnails is normal, not an error.
            thumbnails_artifact = await try_get_artifact_by_slug(env.project_id, "design-thumbnails")  # returns None instead of raising
            ctx.input_artifacts["thumbnails"] = thumbnails_artifact             # Artifact | None -- generate() must handle both

        elif env.capability == "package":
            # Both deps are HARD -- a missing row here is a real bug, let it raise.
            storyboard_artifact = await get_artifact_by_slug(env.project_id, "content-storyboard")  # ContentAgent's finished output
            seo_artifact = await get_artifact_by_slug(env.project_id, "publishing-seo")              # this agent's own prior capability

            ctx.input_artifacts["storyboard"] = Storyboard.model_validate(storyboard_artifact.payload)  # typed: generate() reads .shots directly
            ctx.input_artifacts["seo"] = SeoMetadata.model_validate(seo_artifact.payload)                # typed: generate() reads .tags directly

        else:
            raise ValueError(f"unknown publishing capability: {env.capability!r}")  # Director sent a node this agent doesn't own

        return ctx                                                              # handed to generate() next

    async def generate(self, ctx: AgentContext) -> Any:
        capability = ctx.envelope.capability
        if capability == "seo":
            return await self._generate_seo(ctx)
        if capability == "package":
            return await self._generate_package(ctx)
        raise ValueError(f"unknown publishing capability: {capability!r}")

    async def _generate_seo(self, ctx: AgentContext) -> SeoMetadata:
        project = ctx.input_artifacts["project"]
        outline: dict = ctx.input_artifacts["outline"]
        thumbnails: Artifact | None = ctx.input_artifacts["thumbnails"]

        sections_block = "\n".join(
            f"- {section.get('title', '')}: {section.get('summary', '')}"
            for section in outline.get("sections", [])
        )

        if thumbnails is not None:
            concepts = thumbnails.payload.get("concepts", [])
            overlays = ", ".join(c.get("overlay_text", "") for c in concepts) or "(none)"
            thumbnail_block = f"Thumbnail overlay text already chosen: {overlays}"
            thumbnail_instruction = (
                "Set thumbnail_alignment_note to one sentence on whether the seo_title "
                "reinforces or conflicts with the thumbnail overlay text above."
            )
        else:
            thumbnail_block = "(no thumbnails have been generated yet)"
            thumbnail_instruction = "Leave thumbnail_alignment_note as null -- do not reference thumbnails."

        prompt = _SEO_PROMPT.format(
            title=outline.get("title", project.title),
            sections_block=sections_block,
            thumbnail_block=thumbnail_block,
            thumbnail_instruction=thumbnail_instruction,
        )
        return await generate_structured(prompt, schema=SeoMetadata, repair_hint=ctx.repair_hint)

    async def _generate_package(self, ctx: AgentContext) -> PublishingPackage:
        # No LLM call -- content.storyboard and publishing.seo are both already
        # fully generated and validated, so this is pure assembly.
        project = ctx.input_artifacts["project"]
        storyboard: Storyboard = ctx.input_artifacts["storyboard"]
        seo: SeoMetadata = ctx.input_artifacts["seo"]

        sections = [
            PackageSection(
                section_key=shot.section_key,
                visual=shot.visual,
                overlay_text=shot.overlay_text,
                duration_s=shot.duration_s,
            )
            for shot in storyboard.shots
        ]

        return PublishingPackage(
            title=project.title,
            seo_title=seo.seo_title,
            seo_description=seo.seo_description,
            tags=seo.tags,
            sections=sections,
        )

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        capability = ctx.envelope.capability
        if capability == "seo":
            return self._validate_seo(generated)
        if capability == "package":
            return self._validate_package(ctx, generated)
        raise ValueError(f"unknown publishing capability: {capability!r}")

    def _validate_seo(self, seo: SeoMetadata) -> ValidationReport:
        # Real, deterministic length checks -- what search engines/platforms
        # actually display before truncating, not arbitrary preferences. Same
        # category as validators/word_budget.check: arithmetic against a
        # budget, not a semantic judgment.
        failures: list[str] = []

        title_len = len(seo.seo_title)
        if title_len > MAX_SEO_TITLE_CHARS:
            failures.append(
                f"seo_title is {title_len} chars, exceeds the {MAX_SEO_TITLE_CHARS}-char cap "
                f"search engines display before truncating: {seo.seo_title!r}"
            )

        description_len = len(seo.seo_description)
        if description_len > MAX_SEO_DESCRIPTION_CHARS:
            failures.append(
                f"seo_description is {description_len} chars, exceeds the "
                f"{MAX_SEO_DESCRIPTION_CHARS}-char cap: {seo.seo_description!r}"
            )
        elif description_len < MIN_SEO_DESCRIPTION_CHARS:
            failures.append(
                f"seo_description is only {description_len} chars, below the "
                f"{MIN_SEO_DESCRIPTION_CHARS}-char minimum -- too thin to be useful search copy: "
                f"{seo.seo_description!r}"
            )

        if not failures:
            return ValidationReport(ok=True)

        return ValidationReport(
            ok=False,
            failures=failures,
            repair_hint=(
                f"Rewrite seo_title to at most {MAX_SEO_TITLE_CHARS} characters and seo_description to "
                f"{MIN_SEO_DESCRIPTION_CHARS}-{MAX_SEO_DESCRIPTION_CHARS} characters. " + " ".join(failures)
            ),
        )

    def _validate_package(self, ctx: AgentContext, package: PublishingPackage) -> ValidationReport:
        # _generate_package is pure assembly (no LLM, no randomness), so this
        # can't self-heal via repair_hint the way the other agents' retries
        # do -- a coverage gap here means a real bug in the mapping logic, not
        # a bad LLM draft. Still worth checking: it surfaces that bug loudly
        # (ok=False after max_attempts) instead of silently shipping an
        # incomplete package. Same shape as ContentAgent._validate_storyboard's
        # coverage check.
        storyboard: Storyboard = ctx.input_artifacts["storyboard"]
        expected_keys = {shot.section_key for shot in storyboard.shots}
        covered_keys = {section.section_key for section in package.sections}
        missing = sorted(expected_keys - covered_keys)

        if not missing:
            return ValidationReport(ok=True)

        return ValidationReport(
            ok=False,
            failures=[f"storyboard section(s) not carried into package: {', '.join(missing)}"],
            repair_hint=f"Package is missing section(s) from the storyboard: {', '.join(missing)}.",
        )

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        capability = ctx.envelope.capability
        if capability == "seo":
            return self._build_seo_output(generated)
        if capability == "package":
            return self._build_package_output(generated)
        raise ValueError(f"unknown publishing capability: {capability!r}")

    def _build_seo_output(self, seo: SeoMetadata) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="publishing_seo",
            slug="publishing-seo",
            payload=seo.model_dump(),
            summary=seo.seo_title,
            model=GEMINI_MODEL,
        )

    def _build_package_output(self, package: PublishingPackage) -> AgentResult:
        # No LLM call happened in _generate_package (pure assembly), so
        # model=None reflects that honestly rather than implying this was
        # LLM-generated.
        #
        # Deliberately NOT calling services/export.py here: export.py's job
        # (per its own TODO) is building the GET /projects/{id}/export
        # response -- a route concern that reads the *persisted*
        # publishing_package artifact back out later, on demand. This is the
        # DAG's terminal node (nothing depends on publishing.package), so
        # there's nothing left to hand off to at generation time either way.
        return AgentResult(
            ok=True,
            artifact_type="publishing_package",
            slug="publishing-package",
            payload=package.model_dump(),
            summary=f"{len(package.sections)} sections, ready to publish",
            model=None,
        )
