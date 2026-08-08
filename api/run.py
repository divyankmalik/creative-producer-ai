"""Local dev entrypoint: `python run.py` instead of `python -m uvicorn app.main:app`.

`python -m uvicorn app.main:app` creates uvicorn's event loop (via
`asyncio.run()`) BEFORE it ever imports `app.main` -- so the
WindowsSelectorEventLoopPolicy fix living inside that module (needed for
psycopg's async mode, which can't run on Windows' default ProactorEventLoop)
gets applied after the loop already exists, which is too late to change it.
Setting the policy here, before uvicorn.run() is even called, means the loop
uvicorn creates honors it from the start.
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
