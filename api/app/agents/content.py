"""Content agent: produces `content.outline`, `content.script.sN`, `content.storyboard`."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import AgentResult, TaskEnvelope, ValidationReport


class ContentAgent(BaseAgent):
    agent_name = "content"

    # capabilities: outline, script, storyboard

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        # TODO: load input artifacts (research.brief or content.outline) by slug.
        raise NotImplementedError

    async def generate(self, ctx: AgentContext) -> Any:
        # TODO: dispatch on ctx.envelope.capability (outline/script/storyboard)
        # and call llm/structured.py accordingly.
        raise NotImplementedError

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        # TODO: for `script`, enforce validators/word_budget.check against
        # ctx.envelope.word_budget.
        raise NotImplementedError

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        # TODO: wrap generated content into AgentResult with the right artifact_type.
        raise NotImplementedError
