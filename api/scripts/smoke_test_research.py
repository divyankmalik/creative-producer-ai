"""Run ResearchAgent against real Gemini/Tavily/Supabase against one seeded
project, and print the resulting AgentResult.

Usage: .venv/Scripts/python.exe scripts/smoke_test_research.py <project_id>
(or set PROJECT_ID in the environment / .env)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.research import ResearchAgent  # noqa: E402
from app.models import TaskEnvelope  # noqa: E402


async def main() -> None:
    project_id_raw = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROJECT_ID")
    if not project_id_raw:
        raise SystemExit("Usage: smoke_test_research.py <project_id> (or set PROJECT_ID)")

    envelope = TaskEnvelope(
        project_id=UUID(project_id_raw),
        node_key="research.brief",
        agent="research",
        capability="brief",
        attempt=1,
    )

    result = await ResearchAgent().run(envelope)

    print(f"ok: {result.ok}")
    if result.ok:
        print(f"artifact_type: {result.artifact_type}")
        print(f"slug: {result.slug}")
        print(f"summary: {result.summary}")
        print(f"model: {result.model}")
        print("payload:")
        import json

        print(json.dumps(result.payload, indent=2))
    else:
        print(f"error_code: {result.error_code}")
        print(f"error_message: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
