from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Setting


def defaults() -> dict[str, Any]:
    return {
        "support_username": "tezis_support",
        "referral_bonus_minor": settings.referral_bonus_minor,
        "free_neurons": settings.free_neurons,
        "maintenance_mode": False,
        "community_chat_id": settings.community_chat_id,
        "stars_rub_rate": settings.stars_rub_rate,
    }


async def get_value(session: AsyncSession, key: str, default: Any = None) -> Any:
    row = await session.get(Setting, key)
    if row is not None:
        return row.value
    if default is not None:
        return default
    return defaults().get(key)


async def get_all(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.scalars(select(Setting))).all()
    result = defaults()
    for row in rows:
        result[row.key] = row.value
    return result


async def set_value(session: AsyncSession, key: str, value: Any) -> Setting:
    row = await session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()
    await session.refresh(row)
    return row


async def set_many(session: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        row = await session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    await session.commit()
    return await get_all(session)


async def get_int(session: AsyncSession, key: str, default: int = 0) -> int:
    value = await get_value(session, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def get_float(session: AsyncSession, key: str, default: float = 0.0) -> float:
    value = await get_value(session, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def get_bool(session: AsyncSession, key: str, default: bool = False) -> bool:
    value = await get_value(session, key, default)
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}
