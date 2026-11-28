from __future__ import annotations

import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_tezis.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"

if not TEST_DB.name.startswith("test_"):  # pragma: no cover - sanity guard
    raise RuntimeError("Tests must use a dedicated test database")

# Never let an ambient production DATABASE_URL reach drop_all() below.
os.environ["APP_ENV"] = "dev"
os.environ["DEV_PAYMENTS_ENABLED"] = "true"
os.environ["BOT_MODE"] = "polling"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-with-32-bytes-min")
os.environ["WEBHOOK_SECRET"] = "test-webhook-secret-with-32-bytes-min"
os.environ.setdefault("DEV_ADMIN_EMAIL", "owner@test.local")
os.environ.setdefault("DEV_ADMIN_PASSWORD", "test-password-123")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
# Unit tests must not call a real search provider from a local .env.
os.environ["SEARXNG_URL"] = ""
# Unit tests must not call a paid AI provider from a local .env.
os.environ["AI_PROVIDER"] = "mock"
os.environ["AI_API_KEY"] = ""
os.environ["FREE_NEURONS"] = "500"
os.environ["AI_NEURONS_PER_1K_TOKENS"] = "25"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.core.db import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models import Product, User, UserRole
from app.services import llm, users
from app.services.llm import Completion


@pytest_asyncio.fixture
async def session():
    async with db_module.engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.drop_all)
        await conn.run_sync(db_module.Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def user(session) -> User:
    created, _ = await users.get_or_create_user(
        session, tg_id=10001, username="tester", first_name="Тест"
    )
    return created


@pytest_asyncio.fixture
async def referrer(session) -> User:
    created, _ = await users.get_or_create_user(
        session, tg_id=10002, username="partner", first_name="Партнёр"
    )
    return created


@pytest_asyncio.fixture
async def product(session) -> Product:
    item = Product(
        slug="test-plan",
        title="Test Plan",
        description="Тестовый тариф",
        kind="subscription",
        price_minor=99000,
        price_stars=762,
        duration_days=30,
        neurons_per_week=100.0,
        brand_limit=1,
        features=["тест"],
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@pytest_asyncio.fixture
async def digital_product(session) -> Product:
    item = Product(
        slug="test-digital",
        title="Test Digital",
        description="Тестовый файл",
        kind="digital",
        price_minor=149000,
        price_stars=1146,
        file_key="products/content-plan-30-days.md",
        features=["тест"],
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@pytest_asyncio.fixture
async def owner(session) -> User:
    created, _ = await users.get_or_create_user(
        session, tg_id=10000, username="owner", first_name="Владелец"
    )
    created.role = UserRole.OWNER.value
    await session.commit()
    return created


@pytest.fixture
def owner_headers(owner: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(owner.id), tg_id=owner.tg_id, role=owner.role
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=str(user.id), tg_id=user.tg_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(session, owner):
    app.state.bot = None
    app.state.dp = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest_asyncio.fixture
async def staff_client(client, owner_headers):
    client.headers.update(owner_headers)
    return client


@pytest.fixture
def fake_chat_llm(monkeypatch: pytest.MonkeyPatch):
    """Stand in for a real provider; records the exact messages sent to it."""
    calls: list[list[dict[str, str]]] = []

    async def complete(
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens=None,
        client=None,
    ) -> Completion:
        calls.append([dict(item) for item in messages])
        return Completion(text="Ответ модели", tokens=120, neurons=3.0)

    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "complete_with_usage", complete)
    return calls


async def get_user_by_tg(session, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))
