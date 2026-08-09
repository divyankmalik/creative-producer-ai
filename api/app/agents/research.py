"""Research agent: produces the `research.brief` artifact.

Root node of the DAG — no input artifacts. Pulls the project idea/params,
grounds itself with a Tavily search, then asks the LLM for a structured brief.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, BaseAgent
from app.llm.client import GEMINI_MODEL
from app.llm.search import SearchResult
from app.llm.search import search as tavily_search
from app.llm.structured import generate_structured
from app.models import AgentResult, TaskEnvelope, ValidationReport
from app.services.projects import get_project
from app.validators.claims import check_grounding, extract_claims


class Source(BaseModel):
    title: str
    url: str
    excerpt: str


class ResearchBrief(BaseModel):
    angle: str
    audience_insight: str
    key_points: list[str] = Field(min_length=3, max_length=8)
    sources: list[Source]


_PROMPT_TEMPLATE = """You are researching a piece of content before it's written.

Idea: {idea}
Target audience: {audience}
Tone: {tone}

Here are your sources -- if one is labeled "Product/feature details you
provided", that's not from the web, it's what you were told directly about
this specific product/feature, and is the authoritative source for anything
specific to it:
{sources_block}

Produce a research brief: a distinct angle for this content, one sentence of
audience insight, 3-8 key points a script could be built from, and the sources
that support them. Every key point must be traceable to one of the sources above
— do not invent facts that aren't in the sources. Prefer the "Product/feature
details you provided" source (when present) for any product-specific claims.
"""


class ResearchAgent(BaseAgent):
    agent_name = "research"

    # capabilities: brief

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        project = await get_project(env.project_id)

        # Lets a user ground content in facts a web search can't find --
        # e.g. an unreleased or internal feature. check_grounding (called in
        # validate()) only does keyword-overlap matching against whatever's
        # in `sources`, so without this there was no way for the user's own
        # facts to ever count as a legitimate source: the LLM is explicitly
        # told not to invent facts absent from the sources, so it either had
        # to stay vague or violate that instruction to say anything specific
        # about a proprietary feature at all.
        #
        # Skips the web search entirely in this case, not just adds to it --
        # live-tested with a real product name ("Smart Filters") that
        # coincidentally collided with an unrelated real product; the web
        # search result got blended into the brief alongside the real
        # reference material, mixing in a competitor's actual claims. If the
        # user is telling us the facts directly, a web search on the same
        # idea text is more likely to introduce noise like that than to add
        # anything useful.
        reference_material = project.params.get("reference_material")
        if reference_material:
            sources = [SearchResult(title="Product/feature details you provided", url="user-provided", content=reference_material)]
        else:
            sources = await tavily_search(project.idea, max_results=5)

        ctx = AgentContext(envelope=env)
        ctx.input_artifacts["project"] = project
        ctx.input_artifacts["sources"] = sources
        return ctx

    async def generate(self, ctx: AgentContext) -> ResearchBrief:
        project = ctx.input_artifacts["project"]
        sources = ctx.input_artifacts["sources"]
        sources_block = (
            "\n".join(f"- ({source.title}, {source.url}) {source.content}" for source in sources)
            or "(no sources found)"
        )

        prompt = _PROMPT_TEMPLATE.format(
            idea=project.idea,
            audience=project.params.get("audience", "general audience"),
            tone=project.params.get("tone", "conversational"),
            sources_block=sources_block,
        )
        return await generate_structured(prompt, schema=ResearchBrief, repair_hint=ctx.repair_hint)

    async def validate(self, ctx: AgentContext, generated: ResearchBrief) -> ValidationReport:
        source_texts = [f"{source.title} {source.excerpt}" for source in generated.sources]
        claims = extract_claims(" ".join(generated.key_points))
        return check_grounding(claims, source_texts)

    async def build_output(self, ctx: AgentContext, generated: ResearchBrief) -> AgentResult:
        return AgentResult(
            ok=True,
            artifact_type="research_brief",
            slug="research-brief",
            payload=generated.model_dump(),
            summary=generated.angle,
            model=GEMINI_MODEL,
        )
