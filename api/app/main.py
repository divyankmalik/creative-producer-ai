"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import sys

from fastapi import FastAPI, HTTPException

from app.db import get_supabase
from app.routes import artifacts, gates, projects

# psycopg's async mode (used by the LangGraph Postgres checkpointer) can't run
# on Windows' default ProactorEventLoop -- it raises
# "Psycopg cannot use the 'ProactorEventLoop' to run in async mode" the first
# time a checkpointed graph touches the DB. Must be set before uvicorn starts
# its event loop, so this runs at import time, not inside a startup hook.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(title="showrunner")

app.include_router(projects.router)
app.include_router(artifacts.router)
app.include_router(gates.router)


@app.get("/health")
async def health() -> dict[str, str]:
    def _ping():
        return get_supabase().table("projects").select("id").limit(1).execute()

    try:
        await asyncio.to_thread(_ping)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc

    return {"status": "ok"}
