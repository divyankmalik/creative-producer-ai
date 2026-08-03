"""Publishing agent: produces `publishing.seo`, `publishing.package`."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import AgentResult, TaskEnvelope, ValidationReport


class PublishingAgent(BaseAgent):
    agent_name = "publishing"

    # capabilities: seo, package

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        # TODO: load content.outline / design.thumbnails (seo) or
        # content.storyboard / publishing.seo (package).
        raise NotImplementedError

    async def generate(self, ctx: AgentContext) -> Any:
        # TODO: dispatch on ctx.envelope.capability and call llm/structured.py.
        raise NotImplementedError

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        # TODO: for `seo`, validate title/description length constraints.
        raise NotImplementedError

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        # TODO: for `package`, call services/export.py to assemble the final bundle.
        raise NotImplementedError
