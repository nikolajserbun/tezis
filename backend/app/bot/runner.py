from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from app.bot.commands import COMMANDS
from app.bot.dispatcher import build_dispatcher
from app.core.config import settings
from app.core.db import create_all, engine
from app.core.logging import configure_logging, get_logger


async def main() -> None:
    configure_logging()
    logger = get_logger("bot")
    if not settings.bot_token:
        raise SystemExit(
            "BOT_TOKEN is not set. Заполните .env по образцу .env.example."
        )

    if settings.auto_create_tables and not settings.is_prod:
        await create_all()
        logger.info("tables_ready")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    try:
        try:
            await bot.set_my_commands(COMMANDS)
        except TelegramNetworkError as exc:
            logger.warning("bot_commands_not_set", error=str(exc))
        logger.info("bot_started", mode="polling")
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
