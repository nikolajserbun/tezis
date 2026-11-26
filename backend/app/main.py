from __future__ import annotations

from contextlib import asynccontextmanager

import sentry_sdk
from aiogram import Bot
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
from app.core.security import SecurityError


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger = get_logger("startup")
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

    if settings.auto_create_tables and not settings.is_prod:
        await create_all()
        logger.info("tables_ready", env=settings.app_env)

    if settings.is_prod and settings.bot_mode != "webhook":
        raise RuntimeError("BOT_MODE=webhook is required in production")
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
        await bot.set_webhook(
            url,
            allowed_updates=dp.resolve_used_update_types(),
            secret_token=settings.webhook_secret,
            drop_pending_updates=False,
        )
        logger.info("webhook_set", url=url)
        try:
            await bot.set_my_commands(COMMANDS)
        except TelegramNetworkError as exc:
            logger.warning("bot_commands_not_set", error=str(exc))

    try:
        yield
    finally:
        if bot is not None:
            await bot.session.close()
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
