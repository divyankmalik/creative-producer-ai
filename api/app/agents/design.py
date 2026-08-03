"""Design agent: produces `design.visual_language`, `design.thumbnails`."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import AgentResult, TaskEnvelope, ValidationReport


class DesignAgent(BaseAgent):
    agent_name = "design"

    # capabilities: visual_language, thumbnails

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        # TODO: load content.outline (and design.visual_language for thumbnails).
        raise NotImplementedError

    async def generate(self, ctx: AgentContext) -> Any:
        # TODO: dispatch on ctx.envelope.capability and call llm/structured.py.
        raise NotImplementedError

    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        # TODO: run validators/design_rules.py (contrast ratio, overlay word cap).
        raise NotImplementedError

    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        # TODO: wrap generated design spec into AgentResult with the right artifact_type.
        raise NotImplementedError
