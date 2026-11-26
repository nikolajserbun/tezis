from __future__ import annotations

from hmac import compare_digest

from aiogram.types import Update
from fastapi import APIRouter, Header, Request

from app.core.config import settings
from app.core.errors import Forbidden, ServiceUnavailable
from app.core.logging import get_logger
from app.services import notifications

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("webhook")


def _secret_is_valid(candidate: str | None) -> bool:
    expected = settings.webhook_secret
    if not expected or expected.startswith("change-me"):
        return False
    return candidate is not None and compare_digest(candidate, expected)


@router.post("/telegram")
@router.post("/telegram/{secret}")
async def telegram_webhook(
    request: Request,
    secret: str | None = None,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Accept Telegram updates without leaking the secret in the URL.

    The legacy path secret is still accepted for older installations, but new
    webhooks are registered with the secret only in the
    ``X-Telegram-Bot-Api-Secret-Token`` header.
    """
    candidate = x_telegram_bot_api_secret_token or secret
    if not _secret_is_valid(candidate):
        raise Forbidden("Invalid webhook secret")

    bot = request.app.state.bot
    dp = request.app.state.dp
    if bot is None or dp is None:
        raise ServiceUnavailable("Bot is not configured")

    try:
        payload = await request.json()
        update = Update.model_validate(payload)
        await dp.feed_update(bot, update)
    except Exception as exc:
        # Telegram retries any non-2xx response. Report the failure to the
        # owner and return 200 so a transient handler error does not cause a
        # retry storm; the error is available in logs/Sentry for recovery.
        logger.exception("webhook_processing_failed", error=str(exc))
        try:
            await notifications.notify_admins(
                bot,
                "❗️ <b>Ошибка обработки webhook Telegram</b>\n\n"
                f"Тип: <code>{type(exc).__name__}</code>\n"
                "Проверьте логи API и статус заказа вручную.",
            )
        except Exception as notify_exc:
            logger.exception("webhook_alert_failed", error=str(notify_exc))

    return {"ok": True}
