from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.worker import (
    cleanup_generation_history,
    cleanup_stale_payments,
    expire_subscriptions,
    retry_deliveries,
    send_scheduled_broadcasts,
)

# Render's free plan has no background worker. When MAINTENANCE_ENABLED=true
# the API process runs the same jobs on a small in-process schedule. Docker and
# local setups keep MAINTENANCE_ENABLED=false and use the ARQ worker instead.
TASKS = (
    ("expire_subscriptions", expire_subscriptions, 3600),
    ("retry_deliveries", retry_deliveries, 1800),
    ("send_scheduled_broadcasts", send_scheduled_broadcasts, 3600),
    ("cleanup_stale_payments", cleanup_stale_payments, 3600),
    ("cleanup_generation_history", cleanup_generation_history, 3600),
)


async def run_forever() -> None:
    logger = get_logger("maintenance")
    await asyncio.sleep(60)
    last_run: dict[str, float | None] = {name: None for name, _, _ in TASKS}
    while True:
        loop = asyncio.get_running_loop()
        now = loop.time()
        for name, task, interval in TASKS:
            last = last_run[name]
            if last is not None and now - last < interval:
                continue
            last_run[name] = now
            try:
                result = await task({})
                logger.info("maintenance_task", task=name, result=result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "maintenance_task_failed", task=name, error=str(exc)
                )
        await asyncio.sleep(60)
