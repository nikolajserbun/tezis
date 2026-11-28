from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.utils import utcnow
from app.models import (
    Payout,
    PayoutStatus,
    Referral,
    ReferralEarning,
    ReferralEarningStatus,
    User,
)
from app.schemas import ReferralStatsOut
from app.services import settings as settings_service


async def capture_referral(session: AsyncSession, referee: User, code: str) -> Referral | None:
    code = code.strip().upper()
    if not code:
        return None
    referrer = await session.scalar(select(User).where(User.referral_code == code))
    if referrer is None or referrer.id == referee.id:
        return None
    if referee.referred_by_id is not None:
        return None

    referee.referred_by_id = referrer.id
    referral = Referral(
        referrer_id=referrer.id,
        referee_id=referee.id,
        code=code,
        status="active",
    )
    session.add(referral)
    await session.flush()
    return referral


async def accrue_for_first_request(
    session: AsyncSession, referee: User
) -> ReferralEarning | None:
    """Pay a fixed bonus once, when a referred friend makes their first request."""
    referral = await session.scalar(
        select(Referral).where(
            Referral.referee_id == referee.id, Referral.status == "active"
        )
    )
    if referral is None:
        return None

    existing = await session.scalar(
        select(ReferralEarning).where(ReferralEarning.referee_id == referee.id)
    )
    if existing is not None:
        return existing

    amount = await settings_service.get_int(
        session, "referral_bonus_minor", settings.referral_bonus_minor
    )
    if amount <= 0:
        return None

    earning = ReferralEarning(
        referral_id=referral.id,
        referee_id=referee.id,
        source="first_request",
        amount_minor=amount,
        rate_bp=0,
        status=ReferralEarningStatus.APPROVED.value,
        approved_at=utcnow(),
    )
    session.add(earning)
    referrer = await session.get(User, referral.referrer_id)
    if referrer is not None:
        referrer.balance_minor += amount
    await session.flush()
    return earning


async def stats(session: AsyncSession, user: User) -> ReferralStatsOut:
    invited = int(
        await session.scalar(
            select(func.count(Referral.id)).where(Referral.referrer_id == user.id)
        )
        or 0
    )
    activated = int(
        await session.scalar(
            select(func.count(func.distinct(ReferralEarning.referee_id)))
            .select_from(ReferralEarning)
            .join(Referral, Referral.id == ReferralEarning.referral_id)
            .where(
                Referral.referrer_id == user.id,
                ReferralEarning.source == "first_request",
                ReferralEarning.status.in_(
                    [
                        ReferralEarningStatus.APPROVED.value,
                        ReferralEarningStatus.PAID.value,
                    ]
                ),
            )
        )
        or 0
    )
    earned = int(
        await session.scalar(
            select(func.coalesce(func.sum(ReferralEarning.amount_minor), 0))
            .select_from(ReferralEarning)
            .join(Referral, Referral.id == ReferralEarning.referral_id)
            .where(
                Referral.referrer_id == user.id,
                ReferralEarning.status.in_(
                    [
                        ReferralEarningStatus.APPROVED.value,
                        ReferralEarningStatus.PAID.value,
                    ]
                ),
            )
        )
        or 0
    )
    pending = int(
        await session.scalar(
            select(func.coalesce(func.sum(ReferralEarning.amount_minor), 0))
            .select_from(ReferralEarning)
            .join(Referral, Referral.id == ReferralEarning.referral_id)
            .where(
                Referral.referrer_id == user.id,
                ReferralEarning.status == ReferralEarningStatus.PENDING.value,
            )
        )
        or 0
    )
    bonus = await settings_service.get_int(
        session, "referral_bonus_minor", settings.referral_bonus_minor
    )
    bot_username = settings.bot_username.lstrip("@")
    return ReferralStatsOut(
        code=user.referral_code,
        link=f"https://t.me/{bot_username}?start=ref_{user.referral_code}",
        invited_count=invited,
        activated_count=activated,
        earned_minor=earned,
        pending_minor=pending,
        balance_minor=user.balance_minor,
        bonus_minor=bonus,
    )


async def request_payout(
    session: AsyncSession,
    *,
    user: User,
    amount_minor: int,
    method: str,
    requisites: str,
) -> Payout:
    if amount_minor < 100_000:
        raise ValidationError("Минимальная сумма вывода — 1 000 ₽")
    if amount_minor > user.balance_minor:
        raise ValidationError("Недостаточно средств на балансе")
    if not requisites.strip():
        raise ValidationError("Укажите реквизиты")

    # Debit in one conditional UPDATE: two parallel payout requests can never
    # both spend the same balance.
    debit = await session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.balance_minor >= amount_minor,
        )
        .values(balance_minor=User.balance_minor - amount_minor)
        .execution_options(synchronize_session="fetch")
    )
    if int(getattr(debit, "rowcount", 0) or 0) != 1:
        raise ValidationError("Недостаточно средств на балансе")

    payout = Payout(
        user_id=user.id,
        amount_minor=amount_minor,
        method=method,
        requisites=requisites.strip(),
        status=PayoutStatus.PENDING.value,
    )
    session.add(payout)
    await session.commit()
    await session.refresh(payout)
    return payout


async def decide_payout(
    session: AsyncSession,
    *,
    payout: Payout,
    admin: User,
    approve: bool,
    note: str = "",
) -> Payout:
    if payout.status != PayoutStatus.PENDING.value:
        raise ValidationError("Заявка уже обработана")
    payout.admin_id = admin.id
    payout.admin_note = note
    payout.processed_at = utcnow()
    if approve:
        payout.status = PayoutStatus.APPROVED.value
    else:
        payout.status = PayoutStatus.REJECTED.value
        user = await session.get(User, payout.user_id)
        if user is not None:
            user.balance_minor += payout.amount_minor
    await session.commit()
    return payout
