"""Human-in-the-loop gate approval."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/projects", tags=["gates"])


class ApproveGateResponse(BaseModel):
    ok: bool
    resumed_node_keys: list[str] = Field(default_factory=list)


@router.post("/{project_id}/gates/{gate_key}/approve", response_model=ApproveGateResponse)
async def approve_gate(project_id: UUID, gate_key: str) -> ApproveGateResponse:
    # TODO: resume the interrupted Director graph checkpoint for this project
    # (director/graph.py, interrupt_before=["gate"]) past `gate_key`.
    raise NotImplementedError
