from __future__ import annotations

from datetime import timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal, create_all, engine
from app.core.logging import configure_logging, get_logger
from app.core.utils import utcnow
from app.models import Broadcast, BroadcastStatus, User
from app.services import ai, broadcasts, chat, community, delivery, notifications, subscriptions


def _bot() -> Bot | None:
    if not settings.bot_token:
        return None
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def expire_subscriptions(ctx: dict) -> dict:
    async with SessionLocal() as session:
        expired = await subscriptions.expire_due(session)
        revoked = 0
        bot = _bot()
        try:
            for sub in expired:
                user = await session.get(User, sub.user_id)
                if user is not None:
                    revoked += await community.revoke_access(session, bot=bot, user=user)
                    await notifications.notify_user(
                        bot,
                        user.tg_id,
                        "⏳ <b>Подписка завершилась</b>\n\n"
                        "Контент и история остаются доступны, но новые генерации "
                        "ограничены. Продлить можно в разделе «Подписка».",
                    )
        finally:
            if bot is not None:
                await bot.session.close()
    return {"expired": len(expired), "revoked": revoked}


async def retry_deliveries(ctx: dict) -> dict:
    async with SessionLocal() as session:
        from app.models import Order, OrderStatus

        rows = list(
            (
                await session.scalars(
                    select(Order).where(Order.status == OrderStatus.PAID.value)
                )
            ).all()
        )
    bot = _bot()
    count = 0
    try:
        async with SessionLocal() as session:
            for order in rows:
                await delivery.fulfill_order(session, order.id, bot=bot)
                count += 1
    finally:
        if bot is not None:
            await bot.session.close()
    return {"retried": count}


async def send_scheduled_broadcasts(ctx: dict) -> dict:
    async with SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(Broadcast).where(
                        Broadcast.status == BroadcastStatus.SCHEDULED.value,
                        Broadcast.scheduled_at.is_not(None),
                        Broadcast.scheduled_at <= utcnow(),
                    )
                )
            ).all()
        )
    bot = _bot()
    sent = 0
    try:
        async with SessionLocal() as session:
            for row in rows:
                await broadcasts.send(session, row, bot)
                sent += 1
    finally:
        if bot is not None:
            await bot.session.close()
    return {"sent": sent}


async def cleanup_stale_payments(ctx: dict) -> dict:
    """Cancel unpaid orders older than 24h so dashboards stay honest."""
    from app.models import Order, OrderStatus

    cutoff = utcnow() - timedelta(hours=24)
    async with SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(Order).where(
                        Order.status == OrderStatus.PENDING.value,
                        Order.created_at < cutoff,
                    )
                )
            ).all()
        )
        for order in rows:
            order.status = OrderStatus.CANCELED.value
            order.canceled_at = utcnow()
        if rows:
            await session.commit()
    return {"canceled": len(rows)}


async def cleanup_generation_history(ctx: dict) -> dict:
    """Drop generations and chat messages older than GENERATION_HISTORY_DAYS."""
    async with SessionLocal() as session:
        removed = await ai.cleanup_old_generations(session)
        messages = await chat.cleanup_old_messages(session)
    return {"removed": removed, "chat_messages": messages}


async def startup(ctx: dict) -> None:
    configure_logging()
    if settings.auto_create_tables and not settings.is_prod:
        await create_all()
    get_logger("worker").info("worker_started")


async def shutdown(ctx: dict) -> None:
    await engine.dispose()


class WorkerSettings:
    functions = [
        expire_subscriptions,
        retry_deliveries,
        send_scheduled_broadcasts,
        cleanup_stale_payments,
        cleanup_generation_history,
    ]
    cron_jobs = [
        cron(expire_subscriptions, minute=5),
        cron(retry_deliveries, minute={15, 45}),
        cron(send_scheduled_broadcasts, minute=0),
        cron(cleanup_stale_payments, minute=30),
        cron(cleanup_generation_history, minute=12),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
