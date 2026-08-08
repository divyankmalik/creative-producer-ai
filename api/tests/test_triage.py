"""Tests for director/triage.py -- pure logic, no mocking needed."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.director.triage import NODE_MAX_ATTEMPTS, Decision, decide
from app.models import AgentResult, NodeStatus, TaskNode

NOW = datetime.now(timezone.utc)


def make_node(attempts: int) -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=uuid4(),
        node_key="research.brief",
        agent="research",
        capability="brief",
        status=NodeStatus.RUNNING,
        attempts=attempts,
        created_at=NOW,
        updated_at=NOW,
    )


def test_successful_result_advances() -> None:
    assert decide(make_node(0), AgentResult(ok=True)) == Decision.ADVANCE
    # even on a later attempt, success is still success
    assert decide(make_node(NODE_MAX_ATTEMPTS), AgentResult(ok=True)) == Decision.ADVANCE


def test_failure_retries_while_under_the_attempt_budget() -> None:
    failure = AgentResult(ok=False, error_code="validation_failed")
    for attempts in range(NODE_MAX_ATTEMPTS):
        assert decide(make_node(attempts), failure) == Decision.RETRY


def test_failure_halts_once_attempt_budget_exhausted() -> None:
    failure = AgentResult(ok=False, error_code="validation_failed")
    assert decide(make_node(NODE_MAX_ATTEMPTS), failure) == Decision.HALT
    assert decide(make_node(NODE_MAX_ATTEMPTS + 5), failure) == Decision.HALT
