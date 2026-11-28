from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.errors import PaymentError
from app.core.utils import ensure_aware, utcnow
from app.models import UsageEvent
from app.services import ai, subscriptions


async def test_free_neuron_limit(session, user) -> None:
    session.add(
        UsageEvent(
            user_id=user.id,
            kind="chat",
            tokens=0,
            neurons=settings.free_neurons,
        )
    )
    await session.commit()

    with pytest.raises(PaymentError, match="Neurons"):
        await ai.generate(
            session, user=user, brand=None, kind="post", platform="telegram", topic="Ещё"
        )


async def test_generation_spends_neurons(session, user) -> None:
    generation = await ai.generate(
        session, user=user, brand=None, kind="post", platform="telegram", topic="Тема"
    )
    assert generation.tokens > 0

    usage = await subscriptions.usage(session, user)
    assert usage.neurons_used > 0
    assert usage.neurons_used == pytest.approx(
        settings.free_neurons - usage.neurons_left
    )
    assert usage.neurons_left < settings.free_neurons


async def test_subscription_weekly_limit_and_reset(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    weekly = float(product.neurons_per_week)
    assert weekly > 0

    allowed, active, is_free, used, limit = await subscriptions.check_limit(session, user)
    assert allowed and active is not None and not is_free
    assert used == 0 and limit == weekly

    await ai.generate(
        session, user=user, brand=None, kind="post", platform="telegram", topic="Один"
    )
    allowed, _active, _free, used, _limit = await subscriptions.check_limit(session, user)
    assert allowed and 0 < used < weekly

    # Fill the rest of the weekly allowance with a direct usage event.
    session.add(
        UsageEvent(
            user_id=user.id,
            subscription_id=sub.id,
            kind="chat",
            tokens=100,
            neurons=weekly,
        )
    )
    await session.commit()
    allowed, _active, _free, used, _limit = await subscriptions.check_limit(session, user)
    assert not allowed and used >= weekly

    usage = await subscriptions.usage(session, user)
    assert usage.has_subscription is True
    assert usage.neurons_left == 0.0
    assert usage.resets_at is not None

    # A new weekly window after the previous one ends resets consumption.
    sub = await subscriptions.get_active(session, user.id)
    assert sub is not None
    sub.current_period_start = utcnow() - timedelta(days=8)
    sub.current_period_end = utcnow() - timedelta(days=1)
    sub.expires_at = utcnow() + timedelta(days=10)
    await session.commit()

    allowed, _active, is_free, used, _limit = await subscriptions.check_limit(session, user)
    assert allowed and not is_free and used == 0


async def test_usage_reports_free_quota(session, user) -> None:
    usage = await subscriptions.usage(session, user)
    assert usage.has_subscription is False
    assert usage.neurons_limit == settings.free_neurons
    assert usage.neurons_used == 0
    assert usage.neurons_left == settings.free_neurons
    # Free Neurons are a lifetime budget: there is no refill date.
    assert usage.resets_at is None


async def test_paid_plan_ignores_free_neuron_limit(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    session.add(
        UsageEvent(
            user_id=user.id,
            subscription_id=sub.id,
            kind="chat",
            tokens=1000,
            neurons=5000.0,
        )
    )
    await session.commit()

    allowed, active, is_free, used, limit = await subscriptions.check_limit(session, user)
    assert not allowed and active is not None and not is_free
    assert used >= limit
    assert limit == float(product.neurons_per_week)

    usage = await subscriptions.usage(session, user)
    assert usage.has_subscription is True
    assert usage.neurons_limit == float(product.neurons_per_week)
    assert usage.neurons_left == 0.0


async def test_extending_same_plan_keeps_weekly_allowance(session, user, product) -> None:
    first = await subscriptions.create_or_extend(session, user=user, product=product)
    weekly = first.neurons_per_week
    first_expiry = ensure_aware(first.expires_at)
    second = await subscriptions.create_or_extend(session, user=user, product=product)
    assert second.id == first.id
    # The plan's weekly allowance does not accumulate; only the end date moves.
    assert second.neurons_per_week == weekly
    assert ensure_aware(second.expires_at) > first_expiry


async def test_expire_due_marks_subscriptions(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    sub.expires_at = utcnow() - timedelta(minutes=1)
    await session.commit()
    expired = await subscriptions.expire_due(session)
    assert len(expired) == 1
    assert expired[0].status == "expired"
