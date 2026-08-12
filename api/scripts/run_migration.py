"""Apply every migrations/*.sql file against DATABASE_URL, in filename order.
One-shot per file, not idempotent (rerunning an already-applied file will
fail on its `create table` / `add column` statements) -- this is meant for
setting up a fresh database, not for tracking which migrations already ran.
If you're adding a new migration to an existing database, run it directly
instead of through this script, or drop/recreate first for a clean setup.

Usage: .venv/Scripts/python.exe scripts/run_migration.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"No .sql files found in {MIGRATIONS_DIR}")
        return

    conn = await asyncpg.connect(database_url)
    try:
        for path in migration_files:
            await conn.execute(path.read_text(encoding="utf-8"))
            print(f"Applied {path.name} successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
