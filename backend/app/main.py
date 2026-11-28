from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.bot.commands import COMMANDS
from app.bot.dispatcher import build_dispatcher
from app.core.config import settings
from app.core.db import create_all, engine
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.monitoring import capture_exception, init_sentry, should_alert
from app.core.rate_limit import limiter
from app.core.security import SecurityError
from app.services import notifications

WEBHOOK_RETRY_DELAYS = (5, 10, 20, 40, 60, 60)


async def _set_webhook_and_commands(
    bot: Bot, dp: Dispatcher, url: str, logger: Any
) -> None:
    await bot.set_webhook(
        url,
        allowed_updates=dp.resolve_used_update_types(),
        secret_token=settings.telegram_webhook_secret,
        drop_pending_updates=False,
    )
    logger.info("webhook_set", url=url)
    try:
        await bot.set_my_commands(COMMANDS)
    except TelegramNetworkError as exc:
        logger.warning("bot_commands_not_set", error=str(exc))


async def _retry_webhook_setup(
    bot: Bot, dp: Dispatcher, url: str, logger: Any
) -> None:
    for delay in WEBHOOK_RETRY_DELAYS:
        await asyncio.sleep(delay)
        try:
            await _set_webhook_and_commands(bot, dp, url, logger)
            logger.info("webhook_setup_recovered")
            return
        except Exception as exc:
            # Includes TelegramUnauthorizedError for a bad token and network
            # errors during cold start. Keep retrying, then alert the owner.
            logger.warning("webhook_setup_retry", delay=delay, error=str(exc))
    logger.error("webhook_setup_failed", url=url)
    await notifications.notify_admins(
        bot,
        "❌ <b>Не удалось установить webhook Telegram</b>\n\n"
        f"URL: <code>{url}</code>\n"
        "Проверьте BOT_TOKEN, WEBHOOK_SECRET и доступность API.",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger = get_logger("startup")
    init_sentry()

    if settings.auto_create_tables and not settings.is_prod:
        await create_all()
        logger.info("tables_ready", env=settings.app_env)

    if settings.is_prod and settings.bot_mode not in {"webhook", "polling"}:
        raise RuntimeError("BOT_MODE must be webhook or polling")
    if (
        settings.is_prod
        and settings.bot_mode == "polling"
        and not settings.allow_prod_polling
    ):
        raise RuntimeError(
            "BOT_MODE=polling in production requires ALLOW_PROD_POLLING=true"
        )
    if settings.is_prod and settings.bot_mode == "webhook":
        if not settings.webhook_base_url:
            raise RuntimeError("WEBHOOK_BASE_URL is required for production webhook")
        if (
            not settings.webhook_secret
            or settings.webhook_secret.startswith("change-me")
        ):
            raise RuntimeError("WEBHOOK_SECRET must be replaced in production")

    bot: Bot | None = None
    dp = None
    webhook_task: asyncio.Task[None] | None = None
    maintenance_task: asyncio.Task[None] | None = None
    if settings.bot_token:
        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = build_dispatcher()
        logger.info("bot_ready", mode=settings.bot_mode)
    else:
        logger.warning("bot_token_missing")

    app.state.bot = bot
    app.state.dp = dp

    if (
        bot is not None
        and dp is not None
        and settings.bot_mode == "webhook"
        and settings.webhook_base_url
    ):
        url = (
            f"{settings.webhook_base_url.rstrip('/')}"
            "/api/v1/webhooks/telegram"
        )
        try:
            await _set_webhook_and_commands(bot, dp, url, logger)
        except TelegramNetworkError as exc:
            logger.warning("webhook_setup_deferred", url=url, error=str(exc))
            if settings.is_serverless:
                # A serverless invocation cannot keep a retry task alive after
                # it responds; the next cold start will try again.
                logger.warning("webhook_setup_retry_skipped_serverless")
                await notifications.notify_admins(
                    bot,
                    "❌ <b>Не удалось установить webhook Telegram</b>\n\n"
                    f"URL: <code>{url}</code>\n"
                    "Проверьте BOT_TOKEN и доступность API.",
                )
            else:
                webhook_task = asyncio.create_task(
                    _retry_webhook_setup(bot, dp, url, logger)
                )

    if settings.is_prod and bot is not None and not settings.is_serverless:
        # Do not slow down startup (and Render's health check) on Telegram.
        alert = asyncio.create_task(
            notifications.notify_admins(
                bot,
                "✅ <b>Tezis API запущен</b>\n\n"
                f"Режим бота: <code>{settings.bot_mode}</code>\n"
                f"Окружение: <code>{settings.app_env}</code>",
            )
        )
        app.state.alert_tasks.add(alert)
        alert.add_done_callback(app.state.alert_tasks.discard)

    if settings.maintenance_enabled and not settings.is_serverless:
        # Imported lazily so local/dev runs do not import the ARQ worker unless
        # they actually use the in-process scheduler. Serverless deployments
        # call /api/v1/internal/maintenance from Vercel Cron instead.
        from app.maintenance import run_forever

        maintenance_task = asyncio.create_task(run_forever())
        logger.info("maintenance_started")

    try:
        yield
    finally:
        for task in (webhook_task, maintenance_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        pending = tuple(app.state.webhook_tasks) + tuple(app.state.alert_tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if bot is not None:
            await bot.session.close()
        await limiter.aclose()
        await engine.dispose()
        logger.info("shutdown")


app = FastAPI(
    title="Tezis API",
    version="0.1.0",
    description=(
        "Telegram AI content studio: bot, catalog, payments, "
        "subscriptions, referrals, admin."
    ),
    lifespan=lifespan,
)

app.state.webhook_tasks = set()
app.state.alert_tasks = set()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


@app.exception_handler(SecurityError)
async def security_error_handler(request: Request, exc: SecurityError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "message": str(exc)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Проверьте правильность заполнения полей",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    get_logger("errors").exception("unhandled_error", path=request.url.path)
    capture_exception(exc)
    if should_alert("unhandled_error"):
        bot = getattr(request.app.state, "bot", None)
        if bot is not None:
            message = (
                "❗️ <b>Необработанная ошибка API</b>\n\n"
                f"Путь: <code>{request.url.path}</code>\n"
                f"Тип: <code>{type(exc).__name__}</code>"
            )
            if settings.is_serverless:
                # A background task would be frozen with the function instance
                # as soon as the response is sent, so deliver it inline.
                await notifications.notify_admins(bot, message)
            else:
                task = asyncio.create_task(notifications.notify_admins(bot, message))
                request.app.state.alert_tasks.add(task)
                task.add_done_callback(request.app.state.alert_tasks.discard)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Внутренняя ошибка сервера"},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"app": "Tezis", "docs": "/docs", "health": "/api/v1/health/live"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
