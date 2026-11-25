from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    kwargs: dict = {"echo": False, "future": True, "pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        kwargs.pop("pool_pre_ping", None)
    return kwargs


engine = create_async_engine(settings.database_url, **_engine_kwargs())
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    # Import models so that metadata is populated before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
