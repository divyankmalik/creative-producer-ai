"""Template-method base class shared by all four specialist agents.

Subclasses only implement the four abstract hooks; the generate -> validate
-> repair control flow below is the architecture and is fully wired.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.models import AgentResult, TaskEnvelope, ValidationReport


@dataclass
class AgentContext:
    """Mutable working state threaded through one `run()` call."""

    envelope: TaskEnvelope
    input_artifacts: dict[str, Any] = field(default_factory=dict)
    repair_hint: str | None = None


class BaseAgent(ABC):
    agent_name: str
    max_attempts: int = 3

    async def run(self, env: TaskEnvelope) -> AgentResult:
        ctx = await self.build_context(env)

        last_report: ValidationReport | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                generated = await self.generate(ctx)
            except (ValueError, ValidationError) as exc:
                # A malformed-JSON or schema-mismatch response from the LLM
                # (e.g. `**"text"**` -- stray markdown breaking JSON syntax,
                # seen live from Groq's fallback model) used to propagate
                # straight out of run() uncaught, skipping this entire
                # repair-hint loop -- every attempt was then a blind,
                # uninformed retry instead of one told exactly what broke.
                # Treated as a validation failure so the *next* attempt's
                # prompt actually includes a hint about what went wrong.
                last_report = ValidationReport(
                    ok=False,
                    failures=[f"generation produced an unparseable response: {exc}"],
                    repair_hint=(
                        f"Your previous response could not be parsed: {exc}. Return ONLY a single valid "
                        "JSON object -- no markdown formatting (no ** or _ emphasis, no code fences) "
                        "anywhere, including inside field values."
                    ),
                )
                ctx.repair_hint = last_report.repair_hint
                continue

            report = await self.validate(ctx, generated)

            if report.ok:
                return await self.build_output(ctx, generated)

            last_report = report
            ctx.repair_hint = report.repair_hint

        failures = last_report.failures if last_report else ["unknown validation failure"]
        return AgentResult(
            ok=False,
            error_code="validation_failed",
            error_message="; ".join(failures),
        )

    @abstractmethod
    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        """Fetch and assemble input_artifact_slugs into ctx.input_artifacts."""

    @abstractmethod
    async def generate(self, ctx: AgentContext) -> Any:
        """Call the LLM (via llm/structured.py) to produce a draft payload.

        Must honor ctx.repair_hint when set (i.e. on retry after a failed
        validation), rather than regenerating blindly from scratch.
        """

    @abstractmethod
    async def validate(self, ctx: AgentContext, generated: Any) -> ValidationReport:
        """Run this agent's validators/* checks against the generated draft."""

    @abstractmethod
    async def build_output(self, ctx: AgentContext, generated: Any) -> AgentResult:
        """Shape a validated draft into the AgentResult persisted as an artifact."""
