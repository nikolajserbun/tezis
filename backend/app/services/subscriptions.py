from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.utils import aware, ensure_aware, utcnow
from app.models import (
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


async def _used_neurons(
    session: AsyncSession,
    user_id: UUID,
    *,
    subscription_id: UUID | None = None,
    since: datetime | None = None,
) -> float:
    """Sum Neurons from usage events, optionally within one subscription period."""
    stmt = select(UsageEvent.neurons, UsageEvent.created_at).where(
        UsageEvent.user_id == user_id
    )
    if subscription_id is None:
        stmt = stmt.where(UsageEvent.subscription_id.is_(None))
    else:
        stmt = stmt.where(UsageEvent.subscription_id == subscription_id)
    rows = (await session.execute(stmt)).all()
    start = ensure_aware(since) if since is not None else None
    total = 0.0
    for value, created in rows:
        if start is not None:
            normalized = ensure_aware(created)
            if normalized is None or normalized < start:
                continue
        total += float(value or 0)
    return total


def _period_length() -> timedelta:
    return timedelta(days=max(settings.subscription_period_days, 1))


def _current_period(sub: Subscription) -> tuple[datetime, datetime]:
    """Return the active weekly window without changing the database row.

    A paid plan refills 7 days after the previous window ends. Free accounts
    never call this: their lifetime budget is never topped up.
    """
    now = utcnow()
    start = aware(sub.current_period_start)
    end = aware(sub.current_period_end)
    expires = aware(sub.expires_at)
    if end <= now and now < expires:
        start = now
        end = min(start + _period_length(), expires)
    return start, min(end, expires)


async def _sync_period(session: AsyncSession, sub: Subscription) -> None:
    start, end = _current_period(sub)
    if start != aware(sub.current_period_start) or end != aware(sub.current_period_end):
        sub.current_period_start = start
        sub.current_period_end = end
        await session.flush()


def _neuron_limit(user: User, base: float) -> float:
    """Plan allowance plus personal bonus; an override replaces the plan value."""
    if user.neurons_limit_override is not None:
        base = float(user.neurons_limit_override)
    return max(base + float(user.neurons_bonus or 0), 0.0)


async def free_neuron_limit(session: AsyncSession) -> float:
    return max(
        await settings_service.get_float(session, "free_neurons", settings.free_neurons),
        0.0,
    )


async def reserve_slot(
    session: AsyncSession, user: User
) -> tuple[bool, Subscription | None, bool, float, float]:
    """Check the Neuron quota while holding the user row for the whole request.

    The provider call can take seconds. Without this lock, parallel requests
    all pass the same "last Neurons" check and overspend the account. Postgres
    serializes on the user row; SQLite is single-writer and needs no FOR UPDATE.
    The caller must commit or roll back the session to release the lock.
    """
    stmt = select(User.id).where(User.id == user.id)
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    await session.execute(stmt)
    return await check_limit(session, user)


async def check_limit(
    session: AsyncSession, user: User
) -> tuple[bool, Subscription | None, bool, float, float]:
    """Return (allowed, subscription, is_free, neurons_used, neurons_limit)."""
    sub = await get_active(session, user.id)
    if sub is not None:
        await _sync_period(session, sub)
        limit = _neuron_limit(user, float(sub.neurons_per_week or 0))
        used = await _used_neurons(
            session, user.id, subscription_id=sub.id, since=sub.current_period_start
        )
        return used < limit, sub, False, used, limit

    # Without a subscription the budget is lifetime: old usage is never reset.
    limit = _neuron_limit(user, await free_neuron_limit(session))
    used = await _used_neurons(session, user.id)
    return used < limit, None, True, used, limit


async def subscription_neuron_usage(
    session: AsyncSession, sub: Subscription
) -> tuple[float, float]:
    """(used, limit) for the current weekly window of a given subscription."""
    start, _end = _current_period(sub)
    used = await _used_neurons(
        session, sub.user_id, subscription_id=sub.id, since=start
    )
    return used, float(sub.neurons_per_week or 0)


async def usage(session: AsyncSession, user: User) -> UsageOut:
    sub = await get_active(session, user.id)
    if sub is not None:
        _start, end = _current_period(sub)
        limit = _neuron_limit(user, float(sub.neurons_per_week or 0))
        used = await _used_neurons(
            session, user.id, subscription_id=sub.id, since=sub.current_period_start
        )
        return UsageOut(
            has_subscription=True,
            plan_title=sub.product.title if sub.product else None,
            neurons_limit=limit,
            neurons_used=used,
            neurons_left=max(limit - used, 0.0),
            resets_at=end,
            expires_at=sub.expires_at,
        )

    limit = _neuron_limit(user, await free_neuron_limit(session))
    used = await _used_neurons(session, user.id)
    return UsageOut(
        has_subscription=False,
        neurons_limit=limit,
        neurons_used=used,
        neurons_left=max(limit - used, 0.0),
        resets_at=None,
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
    weekly = float(product.neurons_per_week or 0)
    current = await get_active(session, user.id)

    if current is not None and current.product_id == product.id:
        current.expires_at = max(aware(current.expires_at), now) + duration
        current.neurons_per_week = weekly
        if aware(current.current_period_end) > aware(current.expires_at):
            current.current_period_end = aware(current.expires_at)
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
        current_period_end=min(now + _period_length(), now + duration),
        expires_at=now + duration,
        auto_renew=False,
        neurons_per_week=weekly,
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
