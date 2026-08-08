"""LangGraph StateGraph wiring for the Director.

Graph shape: plan -> schedule -> {gate | schedule | finalize} , gate -> schedule.
`interrupt_before=["gate"]` pauses the graph so a human can approve via
POST /projects/{id}/gates/{key}/approve before script nodes are unblocked.

DEVIATION FROM THE ORIGINAL BLUEPRINT: the blueprint's `build_graph() ->
StateGraph` signature assumed a plain constructor for the Postgres
checkpointer. The installed `AsyncPostgresSaver` (langgraph-checkpoint-
postgres 2.0.13) isn't one -- `AsyncPostgresSaver.from_conn_string(...)` is
an `@asynccontextmanager`, so a live checkpointer can only be obtained (and
kept alive) inside an `async with` block. Wiring the graph's *shape* is
still a plain sync function (`_wire_graph`, no I/O, easy to unit test);
`build_graph()` is now itself an async context manager that yields a
compiled, checkpointed graph for the duration of the `async with` block:

    async with build_graph() as graph:
        await graph.ainvoke(initial_state(project_id), config=...)
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.content import ContentAgent
from app.agents.design import DesignAgent
from app.agents.publishing import PublishingAgent
from app.agents.research import ResearchAgent
from app.config import get_settings
from app.director import scheduler, template
from app.director.state import DirectorState
from app.director.triage import Decision, decide
from app.models import AgentResult, NodeStatus, ProjectStatus, TaskEnvelope, TaskNode
from app.services import artifacts as artifacts_service
from app.services import task_nodes as task_nodes_service
from app.services.projects import get_project, update_project_status

# Same fix as app/main.py -- psycopg's async mode can't run on Windows'
# default ProactorEventLoop. Repeated here (idempotent) so anything that
# imports this module directly (tests, standalone scripts) is protected too,
# not just the FastAPI app.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "content": ContentAgent,
    "design": DesignAgent,
    "publishing": PublishingAgent,
}

_TERMINAL_STATUSES = (NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.SKIPPED)
_FAILED_PROJECT_STATUSES = (NodeStatus.FAILED, NodeStatus.BLOCKED)

DEFAULT_SECTION_COUNT = 3


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def plan_node(state: DirectorState) -> DirectorState:
    project = await get_project(state["project_id"])
    section_count = project.params.get("section_count", DEFAULT_SECTION_COUNT)

    node_templates = template.expand_template(section_count)
    nodes = await task_nodes_service.create_task_nodes(state["project_id"], node_templates)

    await update_project_status(state["project_id"], ProjectStatus.RUNNING)

    state["nodes"] = nodes
    return state


async def schedule_node(state: DirectorState) -> DirectorState:
    """One "tick": find everything currently ready, dispatch it, persist the
    outcome, and return. route_after_schedule decides whether the graph loops
    back here for another tick, pauses at a gate, or moves to finalize.
    """
    nodes = state["nodes"]
    # Uncapped on purpose: ready_set's max_parallel cap has no notion of
    # gates, so a gated node consuming one of the N slots would silently
    # starve other, unrelated ready work (e.g. publishing.seo) from ever
    # being dispatched before the graph pauses at the gate. Filter gated
    # nodes out first, THEN apply the real parallelism cap below to what's
    # actually dispatchable.
    ready = scheduler.ready_set(nodes, max_parallel=len(nodes))

    dispatchable: list[TaskNode] = []
    for node in ready:
        gate = _gate_blocking(node.node_key)
        if gate is not None and gate.key not in state["approved_gates"]:
            state["pending_gate_key"] = gate.key
            continue
        dispatchable.append(node)
    dispatchable = dispatchable[: state["max_parallel"]]

    if not dispatchable:
        state["done"] = _all_terminal(nodes)
        return state

    for node in dispatchable:
        node.status = NodeStatus.RUNNING
        await task_nodes_service.update_task_node(node.id, status=NodeStatus.RUNNING)

    results = await asyncio.gather(
        *(_run_node(state["project_id"], node) for node in dispatchable),
        return_exceptions=True,
    )

    for node, result in zip(dispatchable, results):
        if isinstance(result, BaseException):
            result = AgentResult(ok=False, error_code="exception", error_message=str(result))
        await _apply_result(state["project_id"], nodes, node, result)

    state["done"] = _all_terminal(nodes)
    return state


async def gate_node(state: DirectorState) -> DirectorState:
    # No-op passthrough -- interrupt_before=["gate"] is what actually pauses
    # execution before this body ever runs. By the time this DOES run (i.e.
    # after the graph has been resumed), a human has already approved via
    # POST /projects/{id}/gates/{key}/approve, which is responsible for
    # adding the key to state["approved_gates"] before resuming. Clearing
    # pending_gate_key here is a defensive no-op, not the actual approval.
    state["pending_gate_key"] = None
    return state


async def finalize_node(state: DirectorState) -> DirectorState:
    has_failure = any(node.status in _FAILED_PROJECT_STATUSES for node in state["nodes"])
    final_status = ProjectStatus.FAILED if has_failure else ProjectStatus.DONE
    await update_project_status(state["project_id"], final_status)
    state["done"] = True
    return state


def route_after_schedule(state: DirectorState) -> Literal["gate", "schedule", "finalize"]:
    if state["pending_gate_key"] is not None:
        return "gate"
    if state["done"]:
        return "finalize"
    return "schedule"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gate_blocking(node_key: str) -> template.GateTemplate | None:
    for gate in template.GATES:
        if node_key.startswith(gate.blocks_node_key_prefix):
            return gate
    return None


def _all_terminal(nodes: list[TaskNode]) -> bool:
    return all(node.status in _TERMINAL_STATUSES for node in nodes)


async def _run_node(project_id: UUID, node: TaskNode) -> AgentResult:
    agent_cls = _AGENT_REGISTRY[node.agent]
    envelope = _build_envelope(project_id, node)
    return await agent_cls().run(envelope)


def _build_envelope(project_id: UUID, node: TaskNode) -> TaskEnvelope:
    params = dict(node.params)
    if node.node_key.startswith("content.script."):
        # ContentAgent.build_context requires params["section_key"]; derived
        # from the node_key rather than stored in task_nodes.params, since
        # it's fully determined by the key itself ("content.script.s1" -> "s1").
        params.setdefault("section_key", node.node_key.rsplit(".", 1)[-1])

    return TaskEnvelope(
        project_id=project_id,
        node_key=node.node_key,
        agent=node.agent,
        capability=node.capability,
        attempt=node.attempts + 1,
        input_artifact_slugs=[template.slug_for_node_key(dep.node_key) for dep in node.dependencies],
        params=params,
        # None -> ContentAgent's script capability falls back to computing
        # its own budget from the outline + project params (see
        # content.py's _section_word_budget). The Director doesn't need to
        # duplicate that arithmetic here.
        word_budget=None,
    )


async def _apply_result(project_id: UUID, nodes: list[TaskNode], node: TaskNode, result: AgentResult) -> None:
    decision = decide(node, result)

    if decision == Decision.ADVANCE:
        await artifacts_service.upsert_artifact(
            project_id=project_id,
            node_key=node.node_key,
            artifact_type=result.artifact_type or node.capability,
            slug=result.slug or template.slug_for_node_key(node.node_key),
            payload=result.payload or {},
            summary=result.summary,
            model=result.model,
        )
        node.status = NodeStatus.SUCCEEDED
        await task_nodes_service.update_task_node(node.id, status=NodeStatus.SUCCEEDED)
        return

    # RETRY, FAIL_SOFT, and HALT all represent a failed attempt.
    new_status = NodeStatus.QUEUED if decision == Decision.RETRY else NodeStatus.FAILED
    node.status = new_status
    await task_nodes_service.update_task_node(
        node.id,
        status=new_status,
        last_error=result.error_message,
        increment_attempts=True,
    )

    # Both cascade to hard-dependents, but with a different terminal status:
    # HALT -> BLOCKED ("couldn't run, something it truly needed failed"),
    # FAIL_SOFT -> SKIPPED ("never got to run because something optional
    # upstream didn't pan out"). Either way dependents MUST land in a real
    # terminal status, not be left QUEUED forever -- see
    # scheduler.block_hard_dependents' docstring for why that would
    # otherwise infinite-loop schedule_node.
    if decision in (Decision.HALT, Decision.FAIL_SOFT):
        cascade_status = NodeStatus.BLOCKED if decision == Decision.HALT else NodeStatus.SKIPPED
        affected_keys = scheduler.block_hard_dependents(nodes, node.node_key, status=cascade_status)
        by_key = {n.node_key: n for n in nodes}
        for key in affected_keys:
            await task_nodes_service.update_task_node(by_key[key].id, status=cascade_status)


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def _wire_graph() -> StateGraph:
    """Pure graph shape -- no I/O, safe to call/inspect without a live DB."""
    graph = StateGraph(DirectorState)

    graph.add_node("plan", plan_node)
    graph.add_node("schedule", schedule_node)
    graph.add_node("gate", gate_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "schedule")
    graph.add_conditional_edges(
        "schedule",
        route_after_schedule,
        {"gate": "gate", "schedule": "schedule", "finalize": "finalize"},
    )
    graph.add_edge("gate", "schedule")
    graph.add_edge("finalize", END)

    return graph


@asynccontextmanager
async def build_graph():
    """Yields a compiled, checkpointed Director graph. See the module
    docstring for why this is an async context manager rather than a plain
    function -- the checkpointer connection lives exactly as long as the
    `async with` block.

    NOTE: calls checkpointer.setup() on every use, which is idempotent but
    does a real DB round trip each time. Fine for now; once app/main.py has
    a startup hook, move the one-time setup() call there instead.
    """
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        graph = _wire_graph()
        yield graph.compile(checkpointer=checkpointer, interrupt_before=["gate"])
