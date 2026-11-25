from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.utils import aware, utcnow
from app.models import (
    Generation,
    Product,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
)
from app.schemas import UsageOut
from app.services import settings as settings_service


async def get_active(session: AsyncSession, user_id: UUID) -> Subscription | None:
    now = utcnow()
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product))
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def _used_free_requests(session: AsyncSession, user_id: UUID) -> int:
    """Free quota covers both studio generations and chat requests."""
    generations = int(
        await session.scalar(
            select(func.count(Generation.id)).where(Generation.user_id == user_id)
        )
        or 0
    )
    # Usage events survive chat history cleanup: clearing a chat must not
    # give the user extra free requests.
    messages = int(
        await session.scalar(
            select(func.count(UsageEvent.id)).where(
                UsageEvent.user_id == user_id, UsageEvent.kind == "chat"
            )
        )
        or 0
    )
    return generations + messages


async def check_limit(
    session: AsyncSession, user: User
) -> tuple[bool, Subscription | None, bool, int, int]:
    """Return (allowed, subscription, is_free, used, limit)."""
    sub = await get_active(session, user.id)
    if sub is not None:
        now = utcnow()
        if aware(sub.current_period_end) <= now:
            # Prepaid multi-month plan: start a fresh quota period.
            duration = max(
                (aware(sub.expires_at) - aware(sub.current_period_start)).days,
                1,
            )
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=min(duration, 30))
            sub.generations_used = 0
            await session.flush()
        limit = max(sub.generations_limit, 0)
        used = sub.generations_used
        return used < limit, sub, False, used, limit

    free_limit = await settings_service.get_int(
        session, "free_generations", settings.free_generations
    )
    used = await _used_free_requests(session, user.id)
    return used < free_limit, None, True, used, free_limit


async def record_generation(session: AsyncSession, sub: Subscription | None) -> None:
    if sub is not None:
        sub.generations_used += 1
        await session.commit()


async def usage(session: AsyncSession, user: User) -> UsageOut:
    sub = await get_active(session, user.id)
    if sub is not None:
        left = max(sub.generations_limit - sub.generations_used, 0)
        return UsageOut(
            has_subscription=True,
            plan_title=sub.product.title if sub.product else None,
            generations_limit=sub.generations_limit,
            generations_used=sub.generations_used,
            generations_left=left,
            free_generations_left=0,
            expires_at=sub.expires_at,
        )

    free_limit = await settings_service.get_int(
        session, "free_generations", settings.free_generations
    )
    used = await _used_free_requests(session, user.id)
    return UsageOut(
        has_subscription=False,
        generations_limit=free_limit,
        generations_used=used,
        generations_left=0,
        free_generations_left=max(free_limit - used, 0),
    )


async def create_or_extend(
    session: AsyncSession,
    *,
    user: User,
    product: Product,
    order_id: UUID | None = None,
) -> Subscription:
    now = utcnow()
    duration = timedelta(days=product.duration_days or 30)
    current = await get_active(session, user.id)

    if current is not None and current.product_id == product.id:
        current.expires_at = max(aware(current.expires_at), now) + duration
        current.current_period_end = current.expires_at
        current.generations_limit += product.generations_per_month or 0
        current.status = SubscriptionStatus.ACTIVE.value
        current.source_order_id = order_id
        await session.flush()
        return current

    if current is not None:
        current.status = SubscriptionStatus.CANCELED.value
        current.expires_at = now

    sub = Subscription(
        user_id=user.id,
        product_id=product.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=now,
        current_period_start=now,
        current_period_end=now + duration,
        expires_at=now + duration,
        auto_renew=False,
        generations_limit=product.generations_per_month or 0,
        generations_used=0,
        source_order_id=order_id,
    )
    session.add(sub)
    await session.flush()
    await session.refresh(sub)
    return sub


async def expire_due(session: AsyncSession) -> list[Subscription]:
    now = utcnow()
    stmt = select(Subscription).where(
        Subscription.status == SubscriptionStatus.ACTIVE.value,
        Subscription.expires_at <= now,
    )
    subs = list((await session.scalars(stmt)).all())
    for sub in subs:
        sub.status = SubscriptionStatus.EXPIRED.value
    if subs:
        await session.commit()
    return subs


async def cancel(session: AsyncSession, sub: Subscription) -> Subscription:
    sub.status = SubscriptionStatus.CANCELED.value
    sub.expires_at = utcnow()
    await session.commit()
    return sub


async def list_active(session: AsyncSession, limit: int = 200) -> list[Subscription]:
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product), selectinload(Subscription.user))
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.expires_at > utcnow(),
        )
        .order_by(Subscription.expires_at)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())
