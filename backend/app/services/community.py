from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utcnow
from app.models import CommunityMember, Subscription, User
from app.services import settings as settings_service


async def _chat_id(session: AsyncSession) -> int:
    configured = await settings_service.get_int(
        session, "community_chat_id", settings.community_chat_id
    )
    return configured or settings.community_chat_id


async def grant_access(
    session: AsyncSession,
    *,
    bot: Bot | None,
    user: User,
    subscription: Subscription | None = None,
) -> CommunityMember | None:
    chat_id = await _chat_id(session)
    if not chat_id or bot is None:
        return None

    existing = await session.scalar(
        select(CommunityMember).where(
            CommunityMember.user_id == user.id,
            CommunityMember.chat_id == chat_id,
            CommunityMember.revoked_at.is_(None),
        )
    )
    if existing is not None:
        return existing

    try:
        link = await bot.create_chat_invite_link(
            chat_id=chat_id,
            member_limit=1,
            name=f"tezis-{user.tg_id}"[:32],
        )
    except Exception:
        return None

    member = CommunityMember(
        user_id=user.id,
        subscription_id=subscription.id if subscription else None,
        chat_id=chat_id,
        invite_link=link.invite_link,
    )
    session.add(member)
    await session.commit()

    try:
        await bot.send_message(
            user.tg_id,
            "🎟 <b>Доступ в закрытый клуб «Тезис»</b>\n\n"
            f"Ваша персональная ссылка: {link.invite_link}\n\n"
            "Ссылка одноразовая. Если не сработала — напишите в поддержку.",
        )
    except Exception:
        pass
    return member


async def revoke_access(
    session: AsyncSession, *, bot: Bot | None, user: User
) -> int:
    chat_id = await _chat_id(session)
    if not chat_id:
        return 0
    members = list(
        (
            await session.scalars(
                select(CommunityMember).where(
                    CommunityMember.user_id == user.id,
                    CommunityMember.chat_id == chat_id,
                    CommunityMember.revoked_at.is_(None),
                )
            )
        ).all()
    )
    if not members:
        return 0
    if bot is not None:
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user.tg_id)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user.tg_id)
        except Exception:
            pass
    now = utcnow()
    for member in members:
        member.revoked_at = now
    await session.commit()
    return len(members)
