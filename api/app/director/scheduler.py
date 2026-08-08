"""Pure scheduling logic for the Director's `schedule` node.

No I/O here — this operates purely on an in-memory list of TaskNode and is
exercised directly by tests/test_scheduler.py.
"""

from __future__ import annotations

from app.models import NodeStatus, TaskNode

_TERMINAL_STATUSES = (NodeStatus.SUCCEEDED, NodeStatus.FAILED)


def ready_set(nodes: list[TaskNode], max_parallel: int = 3) -> list[TaskNode]:
    """Queued nodes whose hard dependencies all succeeded, capped by
    available slots. Soft dependencies never block.
    """
    by_key = {node.node_key: node for node in nodes}
    running_count = sum(1 for node in nodes if node.status == NodeStatus.RUNNING)
    available_slots = max_parallel - running_count
    if available_slots <= 0:
        return []

    ready: list[TaskNode] = []
    for node in nodes:
        if len(ready) >= available_slots:
            break
        if node.status != NodeStatus.QUEUED:
            continue

        hard_deps = [dep for dep in node.dependencies if dep.kind == "hard"]
        hard_deps_satisfied = all(
            (dep_node := by_key.get(dep.node_key)) is not None
            and dep_node.status == NodeStatus.SUCCEEDED
            for dep in hard_deps
        )
        if hard_deps_satisfied:
            ready.append(node)

    return ready


def block_hard_dependents(
    nodes: list[TaskNode], failed_node_key: str, status: NodeStatus = NodeStatus.BLOCKED
) -> list[str]:
    """Mark the transitive hard-dependents of a failed node as `status`.

    `status` defaults to BLOCKED (a HALT in director/triage.py) but can also
    be SKIPPED (a FAIL_SOFT) -- either way, dependents must land in a real
    terminal NodeStatus, not just be left QUEUED. A dependent stuck QUEUED
    forever (its hard dependency will never SUCCEED, but nothing marks it
    terminal either) means finalize_node's "all nodes terminal" check never
    passes, and the Director loops schedule_node forever making no progress.

    Soft dependents are left untouched, and already-terminal nodes are never
    retroactively re-marked. Returns the node_keys that were changed.
    """
    by_key = {node.node_key: node for node in nodes}

    hard_dependents_of: dict[str, list[str]] = {}
    for node in nodes:
        for dep in node.dependencies:
            if dep.kind == "hard":
                hard_dependents_of.setdefault(dep.node_key, []).append(node.node_key)

    affected: list[str] = []
    visited = {failed_node_key}
    frontier = [failed_node_key]

    while frontier:
        current_key = frontier.pop()
        for dependent_key in hard_dependents_of.get(current_key, []):
            if dependent_key in visited:
                continue
            visited.add(dependent_key)
            frontier.append(dependent_key)

            dependent = by_key.get(dependent_key)
            if dependent is None or dependent.status in _TERMINAL_STATUSES:
                continue

            dependent.status = status
            affected.append(dependent_key)

    return affected
