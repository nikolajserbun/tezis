from __future__ import annotations

import asyncio
from hmac import compare_digest

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Header, Request

from app.core.config import settings
from app.core.errors import Forbidden, ServiceUnavailable, ValidationError
from app.core.logging import get_logger
from app.core.monitoring import capture_exception, should_alert
from app.services import notifications

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("webhook")


def _secret_is_valid(candidate: str | None) -> bool:
    expected = settings.webhook_secret
    if not expected or expected.startswith("change-me"):
        return False
    return candidate is not None and compare_digest(
        candidate, settings.telegram_webhook_secret
    )


async def _process_update(
    bot: Bot, dp: Dispatcher, update: Update, *, propagate: bool = False
) -> None:
    try:
        await dp.feed_update(bot, update)
    except Exception as exc:
        # Log and alert first. On serverless the caller must answer non-2xx so
        # Telegram retries: the function is frozen after the response and no
        # background job can recover a failed payment/order update. A long-
        # running server keeps the old fire-and-forget behaviour to avoid a
        # retry storm on transient handler errors.
        logger.exception("webhook_processing_failed", error=str(exc))
        capture_exception(exc)
        if should_alert("webhook_processing"):
            try:
                await notifications.notify_admins(
                    bot,
                    "❗️ <b>Ошибка обработки webhook Telegram</b>\n\n"
                    f"Тип: <code>{type(exc).__name__}</code>\n"
                    "Проверьте логи API и статус заказа вручную.",
                )
            except Exception as notify_exc:
                logger.exception("webhook_alert_failed", error=str(notify_exc))
        if propagate:
            raise


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

    On a long-running server the update is processed in the background so
    Telegram gets a fast 200. On serverless (Vercel) it is processed inline,
    because the function is frozen as soon as the response is sent.
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
    except Exception as exc:
        logger.exception("webhook_payload_invalid", error=str(exc))
        raise ValidationError("Некорректный Telegram update") from exc

    if settings.is_serverless:
        # Vercel freezes the instance as soon as the response is sent, so the
        # bot must finish before Telegram receives the 200, and any failure
        # must be visible to Telegram as a non-2xx response.
        try:
            await _process_update(bot, dp, update, propagate=True)
        except Exception as exc:
            # AppError is handled without re-raising, so Telegram receives a
            # clean 503 and will retry the update.
            raise ServiceUnavailable(
                "Не удалось обработать обновление Telegram"
            ) from exc
        return {"ok": True}

    task = asyncio.create_task(_process_update(bot, dp, update))
    request.app.state.webhook_tasks.add(task)
    task.add_done_callback(request.app.state.webhook_tasks.discard)
    return {"ok": True}
