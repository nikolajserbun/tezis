from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.errors import PaymentError, ValidationError
from app.models import UsageEvent
from app.services import ai, chat, referrals


async def test_referral_bonus_after_first_request(session, user, referrer) -> None:
    referral = await referrals.capture_referral(session, user, referrer.referral_code)
    await session.commit()
    assert referral is not None

    await chat.ask(
        session,
        user=user,
        brand=None,
        message="Расскажи про тарифы",
        web_search=False,
    )
    await session.refresh(referrer)
    assert referrer.balance_minor == 2500

    await chat.ask(
        session,
        user=user,
        brand=None,
        message="А про рефералы?",
        web_search=False,
    )
    await session.refresh(referrer)
    assert referrer.balance_minor == 2500

    stats = await referrals.stats(session, referrer)
    assert stats.invited_count == 1
    assert stats.activated_count == 1
    assert stats.earned_minor == 2500
    assert stats.bonus_minor == 2500
    assert f"ref_{referrer.referral_code}" in stats.link


async def test_first_studio_generation_also_activates_bonus(session, user, referrer) -> None:
    await referrals.capture_referral(session, user, referrer.referral_code)
    await session.commit()

    await ai.generate(
        session,
        user=user,
        brand=None,
        kind="post",
        platform="telegram",
        topic="Позиционирование эксперта",
    )
    await session.refresh(referrer)
    assert referrer.balance_minor == 2500


async def test_no_bonus_when_quota_is_exhausted(session, user, referrer) -> None:
    await referrals.capture_referral(session, user, referrer.referral_code)
    await session.commit()

    # The first request pays the referral bonus once.
    await chat.ask(
        session,
        user=user,
        brand=None,
        message="Первый вопрос",
        web_search=False,
    )
    await session.refresh(referrer)
    assert referrer.balance_minor == 2500

    session.add(
        UsageEvent(user_id=user.id, kind="chat", tokens=0, neurons=settings.free_neurons)
    )
    await session.commit()

    with pytest.raises(PaymentError, match="Neurons"):
        await chat.ask(
            session,
            user=user,
            brand=None,
            message="Ещё вопрос",
            web_search=False,
        )
    await session.refresh(referrer)
    assert referrer.balance_minor == 2500


async def test_self_referral_is_ignored(session, user) -> None:
    referral = await referrals.capture_referral(session, user, user.referral_code)
    assert referral is None
    assert user.referred_by_id is None


async def test_payout_validation_and_balance(session, user) -> None:
    user.balance_minor = 150000
    await session.commit()

    with pytest.raises(ValidationError):
        await referrals.request_payout(
            session, user=user, amount_minor=50000, method="manual", requisites="card"
        )
    with pytest.raises(ValidationError):
        await referrals.request_payout(
            session, user=user, amount_minor=100000, method="manual", requisites=""
        )

    payout = await referrals.request_payout(
        session,
        user=user,
        amount_minor=100000,
        method="manual",
        requisites="2200 0000 0000 0000",
    )
    assert payout.status == "pending"
    assert user.balance_minor == 50000

    decided = await referrals.decide_payout(
        session, payout=payout, admin=user, approve=False, note="test"
    )
    assert decided.status == "rejected"
    assert user.balance_minor == 150000
