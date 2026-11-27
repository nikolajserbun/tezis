"""One-off and scheduled operations for stateless deployments.

Vercel Functions cannot keep an in-process scheduler alive. The endpoints here
are protected by ``CRON_SECRET`` (Vercel Cron sends it as a bearer token) and
are safe to call manually after a deploy.
"""

from __future__ import annotations

import asyncio
import sys
from hmac import compare_digest
from pathlib import Path
from typing import Any

from alembic.config import Config
from fastapi import APIRouter, Header

from alembic import command
from app.core.config import settings
from app.core.db import engine
from app.core.errors import Forbidden, ServiceUnavailable
from app.core.logging import get_logger
from app.core.monitoring import capture_exception

router = APIRouter(prefix="/internal", tags=["internal"])
logger = get_logger("internal")


def _require_cron_secret(authorization: str | None) -> None:
    secret = settings.cron_secret
    if not secret or secret.startswith("change-me"):
        raise ServiceUnavailable("CRON_SECRET is not configured")
    expected = f"Bearer {secret}"
    if authorization is None or not compare_digest(authorization, expected):
        raise Forbidden("Invalid CRON_SECRET")


@router.get("/maintenance")
async def run_maintenance(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run all periodic jobs once. Called by Vercel Cron."""
    _require_cron_secret(authorization)

    from app.maintenance import TASKS

    results: dict[str, Any] = {}
    for name, task, _interval in TASKS:
        try:
            results[name] = await task({})
        except Exception as exc:
            logger.exception("maintenance_task_failed", task=name, error=str(exc))
            capture_exception(exc)
            results[name] = {"error": type(exc).__name__}
    await engine.dispose()
    return {"status": "ok", "tasks": results}


@router.post("/setup")
async def setup_database(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Apply migrations and seed base data on an empty database.

    Only needed for Vercel, where no start command runs. Safe to repeat:
    Alembic tracks its revision and the seed skips non-empty catalogs.
    """
    _require_cron_secret(authorization)

    backend_dir = Path(__file__).resolve().parents[2]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    alembic_config = Config(str(backend_dir / "alembic.ini"))
    # alembic.ini stores relative paths; resolve them against the bundled
    # backend directory regardless of the function's working directory.
    alembic_config.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_config.set_main_option("prepend_sys_path", str(backend_dir))
    # alembic/env.py uses asyncio.run(), so it must run outside this loop.
    await asyncio.to_thread(command.upgrade, alembic_config, "head")

    from scripts.bootstrap import main as bootstrap

    await bootstrap()
    return {"status": "ok", "migrations": "head"}
