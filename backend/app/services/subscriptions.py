from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.utils import aware, ensure_aware, utcnow
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


async def _used_free_neurons(session: AsyncSession, user_id: UUID) -> float:
    """Neurons spent without a subscription; paid usage has its own quota."""
    return await _used_neurons(session, user_id)


def _generation_limit(user: User, base: int) -> int:
    return max(base + int(user.generations_bonus or 0), 0)


def _neuron_limit(user: User, base: float) -> float:
    """An admin override applies to any user; without it, paid users have no cap."""
    if user.neurons_limit_override is not None:
        return max(float(user.neurons_limit_override) + float(user.neurons_bonus or 0), 0.0)
    if base <= 0:
        return 0.0
    return max(base + float(user.neurons_bonus or 0), 0.0)


async def free_neuron_limit(session: AsyncSession) -> float:
    return max(
        await settings_service.get_float(session, "free_neurons", settings.free_neurons),
        0.0,
    )


async def _paid_neuron_usage(
    session: AsyncSession, user: User, sub: Subscription
) -> tuple[float, float]:
    limit = _neuron_limit(user, 0.0)
    if limit <= 0:
        return 0.0, 0.0
    used = await _used_neurons(
        session, user.id, subscription_id=sub.id, since=sub.current_period_start
    )
    return used, limit


async def check_limit(
    session: AsyncSession, user: User
) -> tuple[bool, Subscription | None, bool, float, float, float, float]:
    """Return (allowed, subscription, is_free, used, limit, neurons_used, neurons_limit)."""
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
        limit = _generation_limit(user, sub.generations_limit)
        used = sub.generations_used
        neurons_used, neurons_limit = await _paid_neuron_usage(session, user, sub)
        allowed = used < limit and (neurons_limit <= 0 or neurons_used < neurons_limit)
        return allowed, sub, False, used, limit, neurons_used, neurons_limit

    neurons_limit = _neuron_limit(user, await free_neuron_limit(session))
    neurons_used = await _used_free_neurons(session, user.id)
    used = await _used_free_requests(session, user.id)
    free_limit = await settings_service.get_int(
        session, "free_generations", settings.free_generations
    )
    return (
        neurons_used < neurons_limit,
        None,
        True,
        used,
        _generation_limit(user, free_limit),
        neurons_used,
        neurons_limit,
    )


async def record_generation(session: AsyncSession, sub: Subscription | None) -> None:
    if sub is not None:
        sub.generations_used += 1
        await session.commit()


async def usage(session: AsyncSession, user: User) -> UsageOut:
    sub = await get_active(session, user.id)
    if sub is not None:
        limit = _generation_limit(user, sub.generations_limit)
        neurons_used, neurons_limit = await _paid_neuron_usage(session, user, sub)
        return UsageOut(
            has_subscription=True,
            plan_title=sub.product.title if sub.product else None,
            generations_limit=limit,
            generations_used=sub.generations_used,
            generations_left=max(limit - sub.generations_used, 0),
            free_generations_left=0,
            neurons_limit=neurons_limit,
            neurons_used=neurons_used,
            neurons_left=max(neurons_limit - neurons_used, 0.0),
            expires_at=sub.expires_at,
        )

    free_limit = await settings_service.get_int(
        session, "free_generations", settings.free_generations
    )
    used = await _used_free_requests(session, user.id)
    neuron_limit = _neuron_limit(user, await free_neuron_limit(session))
    neuron_used = await _used_free_neurons(session, user.id)
    generation_limit = _generation_limit(user, free_limit)
    return UsageOut(
        has_subscription=False,
        generations_limit=generation_limit,
        generations_used=used,
        generations_left=0,
        free_generations_left=max(generation_limit - used, 0),
        neurons_limit=neuron_limit,
        neurons_used=neuron_used,
        neurons_left=max(neuron_limit - neuron_used, 0.0),
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
