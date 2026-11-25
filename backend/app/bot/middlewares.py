from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.db import SessionLocal
from app.services import users


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if tg_user is None or session is None:
            return await handler(event, data)

        user, created = await users.get_or_create_user(
            session,
            tg_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "",
            last_name=tg_user.last_name,
            language=tg_user.language_code or "ru",
        )
        data["user"] = user
        data["is_new_user"] = created
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Simple per-process anti-spam. Redis-based limits are used in the API."""

    def __init__(self, limit: int = 25, window: int = 10) -> None:
        self.limit = limit
        self.window = window
        self.buckets: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        now = time.monotonic()
        bucket = self.buckets[tg_user.id]
        while bucket and bucket[0] <= now - self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            if isinstance(event, Update):
                if event.callback_query is not None:
                    await event.callback_query.answer(
                        "Слишком много действий. Подождите пару секунд.", show_alert=False
                    )
                elif event.message is not None:
                    await event.message.answer("Слишком много сообщений. Подождите пару секунд.")
            return None
        bucket.append(now)
        return await handler(event, data)
