"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.routes import artifacts, gates, projects

app = FastAPI(title="showrunner")

app.include_router(projects.router)
app.include_router(artifacts.router)
app.include_router(gates.router)


@app.get("/health")
async def health() -> dict[str, str]:
    # TODO: ping supabase / db pool, return {"status": "ok"}
    raise NotImplementedError
