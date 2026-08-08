"""Post-execution decision making for a single node's AgentResult."""

from __future__ import annotations

from enum import StrEnum

from app.models import AgentResult, TaskNode

# How many times the Director itself will call agent.run() for one node,
# on top of (not instead of) BaseAgent's own internal generate/validate/
# repair loop (3 LLM attempts per .run() call). This is the outer retry
# budget for whole-node failures -- a crashed build_context, an exception
# from Supabase/Tavily/Gemini, or an agent that still couldn't produce a
# valid draft after its own 3 internal attempts.
NODE_MAX_ATTEMPTS = 2


class Decision(StrEnum):
    ADVANCE = "advance"
    RETRY = "retry"
    FAIL_SOFT = "fail_soft"
    HALT = "halt"


def decide(node: TaskNode, result: AgentResult) -> Decision:
    """FAIL_SOFT is intentionally unreachable with the current four agents --
    none of them emit an error_code meant to be non-fatal to the project.
    It's kept as an option for a future agent/capability that can fail
    without treating its hard-dependents the same way a HALT does: both
    cascade through scheduler.block_hard_dependents, but HALT marks
    dependents BLOCKED ("couldn't run, something it needed truly failed")
    while FAIL_SOFT marks them SKIPPED ("never got a chance to run because
    something optional upstream didn't pan out") -- see graph.py's
    _apply_result.
    """
    if result.ok:
        return Decision.ADVANCE

    if node.attempts < NODE_MAX_ATTEMPTS:
        return Decision.RETRY

    return Decision.HALT
