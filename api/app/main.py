"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

# The frontend (web/) runs on a different origin (localhost:3000) than this
# API (localhost:8000) -- without CORS, the browser blocks every request with
# a "Failed to fetch" before it ever reaches a route, since FastAPI has no
# default OPTIONS preflight handler. Dev-only origins for now; add the real
# deployed frontend origin here once one exists.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
