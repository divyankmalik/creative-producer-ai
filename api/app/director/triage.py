"""Post-execution decision making for a single node's AgentResult."""

from __future__ import annotations

from enum import StrEnum

from app.models import AgentResult, TaskNode


class Decision(StrEnum):
    ADVANCE = "advance"
    RETRY = "retry"
    FAIL_SOFT = "fail_soft"
    HALT = "halt"


def decide(node: TaskNode, result: AgentResult) -> Decision:
    # TODO: inspect result.ok / result.error_code against node.attempts and
    # node.agent's max_attempts to choose ADVANCE / RETRY / FAIL_SOFT / HALT.
    raise NotImplementedError
