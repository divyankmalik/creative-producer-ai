"""Human-in-the-loop gate approval."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import Field

from app.director import template
from app.director.graph import build_graph
from app.models import CamelModel
from app.services.task_nodes import list_task_nodes

router = APIRouter(prefix="/projects", tags=["gates"])


class ApproveGateResponse(CamelModel):
    ok: bool
    resumed_node_keys: list[str] = Field(default_factory=list)


async def _resume_after_gate(project_id: UUID, gate_key: str) -> None:
    """Background job -- resuming can mean several real agent calls (see
    docs/director.md's live-run example: a gate approval led to writing two
    full scripts, a storyboard, and the final package), so this must not
    block the HTTP response the way create_project's initial run doesn't
    either. This is the actual, live-verified resume pattern -- update the
    checkpointed state, then continue from wherever it paused:

        await graph.aupdate_state(config, {"approved_gates": [...]}, as_node="schedule")
        await graph.ainvoke(None, config=config)

    (aupdate_state's `values` is a partial merge per state key, not a full
    replacement -- see graph.py's schedule_node for a real quirk found
    doing this live: writing None to a field can make that key vanish from
    state entirely rather than sticking as an explicit None. Only
    approved_gates is touched here for exactly that reason.)
    """
    try:
        async with build_graph() as graph:
            config = {"configurable": {"thread_id": str(project_id)}}
            snapshot = await graph.aget_state(config)
            approved = list(snapshot.values.get("approved_gates", []))
            if gate_key not in approved:
                approved.append(gate_key)
            await graph.aupdate_state(config, {"approved_gates": approved}, as_node="schedule")
            await graph.ainvoke(None, config=config)
    except Exception as exc:
        print(f"[director] resuming project {project_id} past gate {gate_key!r} crashed: {exc!r}")


@router.post("/{project_id}/gates/{gate_key}/approve", response_model=ApproveGateResponse)
async def approve_gate(
    project_id: UUID,
    gate_key: str,
    background_tasks: BackgroundTasks,
) -> ApproveGateResponse:
    gate = next((g for g in template.GATES if g.key == gate_key), None)
    if gate is None:
        raise HTTPException(status_code=404, detail=f"unknown gate: {gate_key!r}")

    # Reported immediately (the nodes this gate was holding back), not
    # awaited -- the actual resume happens in the background, same as
    # create_project. Poll GET /projects/{id} to see real outcomes.
    nodes = await list_task_nodes(project_id)
    resumed_node_keys = [node.node_key for node in nodes if node.node_key.startswith(gate.blocks_node_key_prefix)]

    background_tasks.add_task(_resume_after_gate, project_id, gate_key)

    return ApproveGateResponse(ok=True, resumed_node_keys=resumed_node_keys)
