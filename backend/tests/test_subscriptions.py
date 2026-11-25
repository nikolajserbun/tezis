from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.errors import PaymentError
from app.core.utils import ensure_aware, utcnow
from app.services import ai, subscriptions


async def test_free_generations_limit(session, user, monkeypatch) -> None:
    monkeypatch.setattr(settings, "free_generations", 1)
    first = await ai.generate(
        session, user=user, brand=None, kind="post", platform="telegram", topic="Тема"
    )
    assert first.result

    with pytest.raises(PaymentError):
        await ai.generate(
            session, user=user, brand=None, kind="post", platform="telegram", topic="Ещё"
        )


async def test_subscription_limits_and_reset(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    sub.generations_limit = 1
    sub.generations_used = 0
    await session.commit()

    allowed, active, is_free, used, limit = await subscriptions.check_limit(session, user)
    assert allowed and not is_free and limit == 1 and used == 0
    assert active is not None

    await ai.generate(
        session, user=user, brand=None, kind="post", platform="telegram", topic="Один"
    )
    allowed, _active, _free, used, _limit = await subscriptions.check_limit(session, user)
    assert not allowed and used == 1

    sub = await subscriptions.get_active(session, user.id)
    assert sub is not None
    sub.current_period_end = utcnow() - timedelta(days=1)
    sub.expires_at = utcnow() + timedelta(days=10)
    await session.commit()

    allowed, _active, is_free, used, _limit = await subscriptions.check_limit(session, user)
    assert allowed and not is_free and used == 0


async def test_usage_reports_free_quota(session, user) -> None:
    usage = await subscriptions.usage(session, user)
    assert usage.has_subscription is False
    assert usage.free_generations_left == settings.free_generations


async def test_extending_same_plan_accumulates(session, user, product) -> None:
    first = await subscriptions.create_or_extend(session, user=user, product=product)
    start_limit = first.generations_limit
    second = await subscriptions.create_or_extend(session, user=user, product=product)
    assert second.id == first.id
    assert second.generations_limit == start_limit * 2
    assert ensure_aware(second.expires_at) > ensure_aware(first.started_at)


async def test_expire_due_marks_subscriptions(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    sub.expires_at = utcnow() - timedelta(minutes=1)
    await session.commit()
    expired = await subscriptions.expire_due(session)
    assert len(expired) == 1
    assert expired[0].status == "expired"
