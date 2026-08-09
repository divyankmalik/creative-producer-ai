"""Tests for agents/base.py's generate -> validate -> repair control flow,
isolated from any specific agent's domain logic via a minimal concrete
subclass.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.base import AgentContext, BaseAgent
from app.models import AgentResult, TaskEnvelope, ValidationReport


def make_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        project_id=uuid4(),
        node_key="test.node",
        agent="test",
        capability="thing",
        attempt=1,
    )


class _StubAgent(BaseAgent):
    """generate() raises `to_raise` on its first `raise_on_attempts` calls,
    then returns a plain string. validate() always accepts.
    """

    agent_name = "test"

    def __init__(self, to_raise: Exception, raise_on_attempts: int) -> None:
        self.to_raise = to_raise
        self.raise_on_attempts = raise_on_attempts
        self.generate_calls = 0
        self.repair_hints_seen: list[str | None] = []

    async def build_context(self, env: TaskEnvelope) -> AgentContext:
        return AgentContext(envelope=env)

    async def generate(self, ctx: AgentContext) -> str:
        self.generate_calls += 1
        self.repair_hints_seen.append(ctx.repair_hint)
        if self.generate_calls <= self.raise_on_attempts:
            raise self.to_raise
        return "ok"

    async def validate(self, ctx: AgentContext, generated: str) -> ValidationReport:
        return ValidationReport(ok=True)

    async def build_output(self, ctx: AgentContext, generated: str) -> AgentResult:
        return AgentResult(ok=True, artifact_type="test", slug="test", payload={}, summary="s")


@pytest.mark.asyncio
async def test_generate_value_error_feeds_repair_hint_instead_of_crashing() -> None:
    """Regression test for a real bug found via live testing: a malformed-JSON
    ValueError from generate() (via llm/structured.py's _parse) used to
    propagate straight out of run(), skipping the repair-hint loop entirely
    -- every attempt was a blind retry with zero information about what went
    wrong, instead of one told the specific parse error and asked to fix it.
    """
    agent = _StubAgent(to_raise=ValueError("LLM response was not valid JSON: boom"), raise_on_attempts=1)
    result = await agent.run(make_envelope())

    assert result.ok is True  # recovered on the 2nd attempt
    assert agent.generate_calls == 2
    assert agent.repair_hints_seen[0] is None  # first attempt: no hint yet
    assert agent.repair_hints_seen[1] is not None
    assert "not valid JSON" in agent.repair_hints_seen[1]


@pytest.mark.asyncio
async def test_generate_repeated_value_errors_exhaust_attempts_without_crashing() -> None:
    agent = _StubAgent(to_raise=ValueError("still broken"), raise_on_attempts=99)
    result = await agent.run(make_envelope())  # must not raise

    assert result.ok is False
    assert result.error_code == "validation_failed"
    assert "still broken" in result.error_message
    assert agent.generate_calls == BaseAgent.max_attempts
