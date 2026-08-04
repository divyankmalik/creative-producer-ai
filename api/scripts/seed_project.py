"""Insert a test `projects` row so there's something for ResearchAgent to
work against, and print its id.

Usage: .venv/Scripts/python.exe scripts/seed_project.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

TEST_TITLE = "Why remote teams burn out on async standups"
TEST_IDEA = (
    "A short video explaining why fully-async daily standups quietly kill remote "
    "team morale, and what teams do instead."
)
TEST_PARAMS = {
    "audience": "engineering managers at remote-first startups",
    "tone": "conversational",
    "target_length_seconds": 240,
}


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        project_id = await conn.fetchval(
            "insert into projects (title, idea, params) values ($1, $2, $3::jsonb) returning id",
            TEST_TITLE,
            TEST_IDEA,
            json.dumps(TEST_PARAMS),
        )
        print(f"Seeded project {project_id}")
        print(f"PROJECT_ID={project_id}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
