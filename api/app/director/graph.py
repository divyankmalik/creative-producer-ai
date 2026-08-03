"""LangGraph StateGraph wiring for the Director.

Graph shape: plan -> schedule -> {gate | schedule | finalize} , gate -> schedule.
`interrupt_before=["gate"]` pauses the graph so a human can approve via
POST /projects/{id}/gates/{key}/approve before script nodes are unblocked.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from app.director.state import DirectorState


async def plan_node(state: DirectorState) -> DirectorState:
    # TODO: expand template.NODE_TEMPLATE (via template.expand_template) into
    # concrete TaskNode rows, persist them, and populate state["nodes"].
    raise NotImplementedError


async def schedule_node(state: DirectorState) -> DirectorState:
    # TODO: call scheduler.ready_set, dispatch each ready node to its agent
    # via agents/*, run triage.decide on results, and update state accordingly.
    raise NotImplementedError


async def gate_node(state: DirectorState) -> DirectorState:
    # TODO: no-op passthrough; the graph is paused here by interrupt_before
    # until POST /projects/{id}/gates/{key}/approve resumes execution.
    raise NotImplementedError


async def finalize_node(state: DirectorState) -> DirectorState:
    # TODO: mark the project status done/failed based on terminal node states.
    raise NotImplementedError


def route_after_schedule(state: DirectorState) -> Literal["gate", "schedule", "finalize"]:
    # TODO: return "gate" if state["pending_gate_key"] is set, "finalize" if
    # state["done"], otherwise "schedule" to keep polling for newly-ready nodes.
    raise NotImplementedError


def build_graph() -> StateGraph:
    # TODO: wire nodes/edges below, compile with a Postgres checkpointer
    # (langgraph.checkpoint.postgres) and interrupt_before=["gate"].
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

    raise NotImplementedError
