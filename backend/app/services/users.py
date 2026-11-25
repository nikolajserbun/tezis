from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_referral_code, utcnow
from app.models import User, UserRole


async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))


async def get_user(session: AsyncSession, user_id: UUID | str) -> User | None:
    return await session.get(User, user_id)


async def _unique_referral_code(session: AsyncSession) -> str:
    for _ in range(20):
        code = generate_referral_code()
        exists = await session.scalar(select(User.id).where(User.referral_code == code))
        if not exists:
            return code
    raise RuntimeError("Could not generate a unique referral code")


async def get_or_create_user(
    session: AsyncSession,
    *,
    tg_id: int,
    username: str | None = None,
    first_name: str = "",
    last_name: str | None = None,
    language: str = "ru",
    start_payload: str | None = None,
) -> tuple[User, bool]:
    user = await get_user_by_tg(session, tg_id)
    if user:
        changed = False
        if username is not None and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name is not None and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        user.last_seen_at = utcnow()
        if changed or True:
            await session.commit()
        return user, False

    user = User(
        tg_id=tg_id,
        username=username,
        first_name=first_name or "Друг",
        last_name=last_name,
        language=language,
        role=UserRole.USER.value,
        referral_code=await _unique_referral_code(session),
        last_seen_at=utcnow(),
    )
    session.add(user)
    await session.flush()

    if start_payload and start_payload.startswith("ref_"):
        from app.services.referrals import capture_referral

        await capture_referral(session, user, start_payload[4:])

    await session.commit()
    await session.refresh(user)
    return user, True


async def update_last_seen(session: AsyncSession, user: User) -> None:
    user.last_seen_at = utcnow()
    await session.commit()


async def ensure_staff(
    session: AsyncSession, tg_id: int, role: str = UserRole.OWNER.value
) -> User | None:
    user = await get_user_by_tg(session, tg_id)
    if not user:
        return None
    user.role = role
    await session.commit()
    return user


async def set_role(session: AsyncSession, user: User, role: str) -> User:
    if role not in {item.value for item in UserRole}:
        raise ValueError("Unknown role")
    user.role = role
    await session.commit()
    return user


async def set_blocked(session: AsyncSession, user: User, blocked: bool) -> User:
    user.is_blocked = blocked
    await session.commit()
    return user


async def adjust_balance(session: AsyncSession, user: User, delta_minor: int) -> User:
    user.balance_minor += delta_minor
    await session.commit()
    return user
