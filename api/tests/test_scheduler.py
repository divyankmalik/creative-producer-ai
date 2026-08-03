from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.director.scheduler import block_hard_dependents, ready_set
from app.models import Dependency, NodeStatus, TaskNode

PROJECT_ID = uuid4()
NOW = datetime.now(timezone.utc)


def make_node(
    node_key: str,
    status: NodeStatus = NodeStatus.QUEUED,
    dependencies: list[Dependency] | None = None,
) -> TaskNode:
    return TaskNode(
        id=uuid4(),
        project_id=PROJECT_ID,
        node_key=node_key,
        agent="content",
        capability="outline",
        status=status,
        dependencies=dependencies or [],
        params={},
        attempts=0,
        last_error=None,
        created_at=NOW,
        updated_at=NOW,
    )


class TestReadySet:
    def test_empty_ready_set_when_nothing_satisfiable(self) -> None:
        nodes = [
            make_node("content.outline", dependencies=[Dependency(node_key="research.brief", kind="hard")]),
            make_node("research.brief", status=NodeStatus.RUNNING),
        ]

        assert ready_set(nodes) == []

    def test_node_with_no_dependencies_is_ready(self) -> None:
        nodes = [make_node("research.brief")]

        assert [n.node_key for n in ready_set(nodes)] == ["research.brief"]

    def test_node_ready_once_hard_dependency_succeeded(self) -> None:
        nodes = [
            make_node("research.brief", status=NodeStatus.SUCCEEDED),
            make_node("content.outline", dependencies=[Dependency(node_key="research.brief", kind="hard")]),
        ]

        assert [n.node_key for n in ready_set(nodes)] == ["content.outline"]

    def test_soft_dependency_never_blocks_readiness(self) -> None:
        nodes = [
            make_node("design.thumbnails", status=NodeStatus.FAILED),
            make_node(
                "publishing.seo",
                dependencies=[
                    Dependency(node_key="content.outline", kind="hard"),
                    Dependency(node_key="design.thumbnails", kind="soft"),
                ],
            ),
            make_node("content.outline", status=NodeStatus.SUCCEEDED),
        ]

        assert [n.node_key for n in ready_set(nodes)] == ["publishing.seo"]

    def test_max_parallel_cap_respected(self) -> None:
        nodes = [make_node(f"content.script.s{i}") for i in range(5)]

        result = ready_set(nodes, max_parallel=2)

        assert len(result) == 2

    def test_running_nodes_consume_available_slots(self) -> None:
        nodes = [
            make_node("research.brief", status=NodeStatus.RUNNING),
            make_node("content.script.s1"),
            make_node("content.script.s2"),
        ]

        result = ready_set(nodes, max_parallel=2)

        assert len(result) == 1


class TestBlockHardDependents:
    def test_hard_dependency_failure_blocks_downstream(self) -> None:
        nodes = [
            make_node("content.outline", status=NodeStatus.FAILED),
            make_node(
                "content.script.s1",
                dependencies=[Dependency(node_key="content.outline", kind="hard")],
            ),
            make_node(
                "content.storyboard",
                dependencies=[Dependency(node_key="content.script.s1", kind="hard")],
            ),
        ]

        blocked = block_hard_dependents(nodes, "content.outline")

        assert set(blocked) == {"content.script.s1", "content.storyboard"}
        by_key = {n.node_key: n for n in nodes}
        assert by_key["content.script.s1"].status == NodeStatus.BLOCKED
        assert by_key["content.storyboard"].status == NodeStatus.BLOCKED

    def test_soft_dependency_failure_does_not_block(self) -> None:
        nodes = [
            make_node("design.thumbnails", status=NodeStatus.FAILED),
            make_node(
                "publishing.seo",
                dependencies=[
                    Dependency(node_key="content.outline", kind="hard"),
                    Dependency(node_key="design.thumbnails", kind="soft"),
                ],
            ),
        ]

        blocked = block_hard_dependents(nodes, "design.thumbnails")

        assert blocked == []
        assert nodes[1].status == NodeStatus.QUEUED

    def test_terminal_nodes_are_not_reblocked(self) -> None:
        nodes = [
            make_node("content.outline", status=NodeStatus.FAILED),
            make_node(
                "content.script.s1",
                status=NodeStatus.SUCCEEDED,
                dependencies=[Dependency(node_key="content.outline", kind="hard")],
            ),
        ]

        blocked = block_hard_dependents(nodes, "content.outline")

        assert blocked == []
        assert nodes[1].status == NodeStatus.SUCCEEDED
