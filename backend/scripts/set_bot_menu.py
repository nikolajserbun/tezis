"""Set the bot menu button to the Mini App at the current FRONTEND_URL.

Run inside the api container:

    docker compose ... exec -T -e PYTHONPATH=/app api python /app/scripts/set_bot_menu.py

BotFather commands (/setmenubutton, /setdomain) still have to be done manually.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.core.config import settings


async def main() -> None:
    url = settings.frontend_url.rstrip("/") + "/app"
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        ok = await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Студия", web_app=WebAppInfo(url=url))
        )
        info = await bot.get_chat_menu_button()
        print(f"OK: menu button -> {url} (set={ok}, type={info.type})")
        print("Remember: BotFather /setdomain is required for the admin Login Widget.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
