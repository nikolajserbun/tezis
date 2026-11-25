from __future__ import annotations

from aiogram.types import Update
from fastapi import APIRouter, Header, Request

from app.core.config import settings
from app.core.errors import Forbidden, ServiceUnavailable

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if secret != settings.webhook_secret and (
        x_telegram_bot_api_secret_token != settings.webhook_secret
    ):
        raise Forbidden("Invalid webhook secret")

    bot = request.app.state.bot
    dp = request.app.state.dp
    if bot is None or dp is None:
        raise ServiceUnavailable("Bot is not configured")

    payload = await request.json()
    update = Update.model_validate(payload)
    await dp.feed_update(bot, update)
    return {"ok": True}
