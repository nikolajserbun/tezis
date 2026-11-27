"""Seed the base data only when the database has no products yet.

Render's free web service has no shell, so the start command runs this after
``alembic upgrade head``. Existing databases (including restored dumps) are left
untouched, which keeps admin edits safe across restarts.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal, engine
from app.models import Product
from scripts.seed_data import main as seed_main


async def main() -> None:
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Product))
    if count:
        print(f"bootstrap: {count} products found, seed skipped")
    else:
        print("bootstrap: no products found, seeding base data")
        sys.argv = ["seed"]
        # Schema is managed by Alembic (the start command runs it first).
        await seed_main(create_schema=False)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
