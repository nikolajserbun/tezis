from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ServiceUnavailable, ValidationError
from app.core.utils import utcnow
from app.models import (
    Broadcast,
    BroadcastDelivery,
    BroadcastStatus,
    Order,
    OrderStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from app.services import analytics


async def create(
    session: AsyncSession,
    *,
    title: str,
    text: str,
    segment: dict,
    created_by_id: UUID | None = None,
    scheduled_at=None,
) -> Broadcast:
    broadcast = Broadcast(
        title=title[:160],
        text=text[:4000],
        segment=segment or {"type": "all"},
        created_by=created_by_id,
        scheduled_at=scheduled_at,
        status=BroadcastStatus.SCHEDULED.value
        if scheduled_at
        else BroadcastStatus.DRAFT.value,
    )
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    return broadcast


async def list_broadcasts(session: AsyncSession, limit: int = 50) -> list[Broadcast]:
    stmt = select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def get_broadcast(session: AsyncSession, broadcast_id: UUID | str) -> Broadcast:
    broadcast = await session.get(Broadcast, broadcast_id)
    if broadcast is None:
        raise NotFound("Рассылка не найдена")
    return broadcast


async def segment_users(session: AsyncSession, segment: dict) -> list[User]:
    kind = (segment or {}).get("type", "all")
    paid = [OrderStatus.PAID.value, OrderStatus.FULFILLED.value]
    stmt = select(User).where(User.is_blocked.is_(False))

    if kind == "payers":
        stmt = stmt.where(
            User.id.in_(select(Order.user_id).where(Order.status.in_(paid)))
        )
    elif kind == "trial":
        stmt = stmt.where(
            ~User.id.in_(select(Order.user_id).where(Order.status.in_(paid)))
        )
    elif kind == "inactive":
        days = int(segment.get("days", 14))
        stmt = stmt.where(
            (User.last_seen_at.is_(None))
            | (User.last_seen_at < utcnow() - timedelta(days=days))
        )
    elif kind == "expiring":
        days = int(segment.get("days", 3))
        stmt = stmt.where(
            User.id.in_(
                select(Subscription.user_id).where(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.expires_at > utcnow(),
                    Subscription.expires_at <= utcnow() + timedelta(days=days),
                )
            )
        )
    elif kind != "all":
        raise ValidationError("Неизвестный сегмент")

    return list((await session.scalars(stmt)).all())


async def send(session: AsyncSession, broadcast: Broadcast, bot: Bot | None) -> Broadcast:
    if bot is None:
        raise ServiceUnavailable("Bot token is not configured")
    if broadcast.status == BroadcastStatus.SENT.value:
        raise ValidationError("Рассылка уже отправлена")

    users = await segment_users(session, broadcast.segment)
    broadcast.status = BroadcastStatus.SENDING.value
    await session.commit()

    sent = 0
    failed = 0
    for index, user in enumerate(users, start=1):
        already = await session.scalar(
            select(BroadcastDelivery).where(
                BroadcastDelivery.broadcast_id == broadcast.id,
                BroadcastDelivery.user_id == user.id,
            )
        )
        if already is not None:
            continue
        try:
            await bot.send_message(user.tg_id, broadcast.text, parse_mode="HTML")
            session.add(
                BroadcastDelivery(
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    status="sent",
                    sent_at=utcnow(),
                )
            )
            sent += 1
        except Exception as exc:
            session.add(
                BroadcastDelivery(
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    status="failed",
                    error=str(exc)[:500],
                )
            )
            failed += 1
        if index % 25 == 0:
            broadcast.sent_count = sent
            broadcast.failed_count = failed
            await session.commit()
        await asyncio.sleep(0.05)

    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.status = BroadcastStatus.SENT.value
    await session.commit()
    await analytics.record_event(
        session,
        "broadcast_sent",
        properties={"broadcast_id": str(broadcast.id), "sent": sent, "failed": failed},
    )
    return broadcast
