from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import (
    admin,
    cart,
    chat,
    content,
    fallback,
    menu,
    payments,
    profile,
    referral,
    shop,
    start,
    subscription,
    support,
)
from app.bot.middlewares import DbSessionMiddleware, ThrottlingMiddleware, UserMiddleware
from app.core.config import settings


def build_dispatcher() -> Dispatcher:
    storage: BaseStorage
    if settings.is_prod:
        storage = RedisStorage.from_url(settings.redis_url)
    else:
        storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(content.router)
    dp.include_router(shop.router)
    dp.include_router(cart.router)
    dp.include_router(subscription.router)
    dp.include_router(profile.router)
    dp.include_router(referral.router)
    dp.include_router(support.router)
    dp.include_router(chat.router)
    dp.include_router(payments.router)
    dp.include_router(fallback.router)
    return dp
