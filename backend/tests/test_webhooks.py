from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import settings
from app.main import app

UPDATE: dict[str, Any] = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1_700_000_000,
        "chat": {"id": 10001, "type": "private"},
        "from": {"id": 10001, "is_bot": False, "first_name": "Tester"},
        "text": "hello",
    },
}


class StubDispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.updates: list[object] = []
        self.fail = fail

    async def feed_update(self, bot: object, update: object) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.updates.append(update)


class BlockingDispatcher:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def feed_update(self, bot: object, update: object) -> None:
        self.started.set()
        await self.release.wait()


async def _drain_webhook_tasks() -> None:
    tasks = tuple(app.state.webhook_tasks)
    if tasks:
        await asyncio.gather(*tasks)


async def test_webhook_accepts_secret_header(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
    )
    await _drain_webhook_tasks()

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(dp.updates) == 1


async def test_webhook_accepts_legacy_path_secret(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        f"/api/v1/webhooks/telegram/{settings.webhook_secret}",
        json=UPDATE,
    )
    await _drain_webhook_tasks()

    assert response.status_code == 200
    assert len(dp.updates) == 1


async def test_webhook_rejects_invalid_secret(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    await _drain_webhook_tasks()

    assert response.status_code == 403
    assert dp.updates == []


async def test_webhook_returns_ok_when_handler_fails(client) -> None:
    app.state.dp = StubDispatcher(fail=True)
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
    )
    await _drain_webhook_tasks()

    # Telegram retries non-2xx responses; a handler error must not cause a storm.
    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_webhook_acks_before_handler_finishes(client) -> None:
    dp = BlockingDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    try:
        response = await client.post(
            "/api/v1/webhooks/telegram",
            json=UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
        )
        await asyncio.wait_for(dp.started.wait(), timeout=2)
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    finally:
        dp.release.set()
        await _drain_webhook_tasks()


async def test_webhook_waits_for_handler_in_serverless(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "vercel", "1")
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()
    before = set(app.state.webhook_tasks)

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(dp.updates) == 1
    assert set(app.state.webhook_tasks) == before
