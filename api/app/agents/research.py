"""Research agent: produces the `research.brief` artifact."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import AgentResult, TaskEnvelope, ValidationReport


class ResearchAgent(BaseAgent):
    agent_name = "research"

    # capabilities: brief

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        # TODO: pull the project idea/params; fetch supporting sources via Tavily.
        raise NotImplementedError

    async def generate(self, ctx: AgentContext) -> Any:
        # TODO: call llm/structured.py to produce a structured research brief.
        raise NotImplementedError

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        # TODO: check brief has required sections and grounded claims (validators/claims.py).
        raise NotImplementedError

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        # TODO: wrap generated brief into AgentResult(artifact_type="research_brief", ...).
        raise NotImplementedError
