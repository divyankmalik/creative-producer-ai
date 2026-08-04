"""Apply migrations/001_init.sql against DATABASE_URL. One-shot, not idempotent
(rerunning against an already-migrated DB will fail on the `create table`
statements) — drop the tables first if you need to re-run it.

Usage: .venv/Scripts/python.exe scripts/run_migration.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import os

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(sql)
        print(f"Applied {MIGRATION_PATH.name} successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
