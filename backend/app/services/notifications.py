from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("notifications")


async def notify_admins(
    bot: Bot | None,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if bot is None:
        return
    chat_id = settings.support_chat_id or settings.admin_chat_id
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as exc:
        logger.warning("admin_notification_failed", error=str(exc))


async def notify_user(
    bot: Bot | None,
    tg_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    if bot is None:
        return False
    try:
        await bot.send_message(tg_id, text, reply_markup=reply_markup)
        return True
    except Exception as exc:
        logger.warning("user_notification_failed", tg_id=tg_id, error=str(exc))
        return False
