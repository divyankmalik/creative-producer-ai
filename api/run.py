"""Entrypoint for both local dev and hosted deployment: `python run.py`
instead of `python -m uvicorn app.main:app`.

`python -m uvicorn app.main:app` creates uvicorn's event loop (via
`asyncio.run()`) BEFORE it ever imports `app.main` -- so the
WindowsSelectorEventLoopPolicy fix living inside that module (needed for
psycopg's async mode, which can't run on Windows' default ProactorEventLoop)
gets applied after the loop already exists, which is too late to change it.
Setting the policy here, before uvicorn.run() is even called, means the loop
uvicorn creates honors it from the start. (This distinction doesn't matter
on Linux -- the underlying ProactorEventLoop bug is Windows-only -- but
using the same entrypoint everywhere means local dev and a hosted deploy
never silently diverge in how the app actually starts.)

PORT is read from the environment since hosting platforms (Render, etc.)
assign it dynamically and expect the app to bind to it; HOST defaults to
0.0.0.0 so it's reachable from outside the container, which is also fine
for local dev (still reachable at localhost).
"""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
