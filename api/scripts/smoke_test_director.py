"""Run the whole Director graph (plan -> schedule -> ...) against real
Gemini/Tavily/Supabase for one freshly-seeded project, end to end up to the
outline_review gate. Never approved here, so the run is expected to pause
there -- that's the correct outcome, not a failure.

Usage: .venv/Scripts/python.exe scripts/smoke_test_director.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.director.graph import build_graph  # noqa: E402
from app.director.state import initial_state  # noqa: E402

TEST_TITLE = "Why remote teams burn out on async standups (director smoke test)"
TEST_IDEA = (
    "A short video explaining why fully-async daily standups quietly kill remote "
    "team morale, and what teams do instead."
)
TEST_PARAMS = {
    "audience": "engineering managers at remote-first startups",
    "tone": "conversational",
    "total_seconds": 180,
    "section_count": 2,  # keep this smoke test cheap/fast
}


async def seed_project() -> UUID:
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        return await conn.fetchval(
            "insert into projects (title, idea, params) values ($1, $2, $3::jsonb) returning id",
            TEST_TITLE,
            TEST_IDEA,
            json.dumps(TEST_PARAMS),
        )
    finally:
        await conn.close()


async def main() -> None:
    project_id = await seed_project()
    print(f"Seeded project {project_id}")

    async with build_graph() as graph:
        config = {"configurable": {"thread_id": str(project_id)}}
        final_state = await graph.ainvoke(initial_state(project_id), config=config)

    print()
    print("=== Final state ===")
    print(f"done: {final_state['done']}")
    print(f"pending_gate_key: {final_state['pending_gate_key']}")
    print()
    print("=== Node statuses ===")
    for node in final_state["nodes"]:
        print(
            f"  {node.node_key:30s} {node.status.value:10s} "
            f"attempts={node.attempts} last_error={node.last_error!r}"
        )


if __name__ == "__main__":
    asyncio.run(main())
