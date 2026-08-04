"""Research agent: produces the `research.brief` artifact.

Root node of the DAG — no input artifacts. Pulls the project idea/params,
grounds itself with a Tavily search, then asks the LLM for a structured brief.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, BaseAgent
from app.llm.client import GEMINI_MODEL
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

Here is what web search turned up on this topic:
{sources_block}

Produce a research brief: a distinct angle for this content, one sentence of
audience insight, 3-8 key points a script could be built from, and the sources
that support them. Every key point must be traceable to one of the sources above
— do not invent facts that aren't in the sources.
"""


class ResearchAgent(BaseAgent):
    agent_name = "research"

    # capabilities: brief

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        project = await get_project(env.project_id)
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
